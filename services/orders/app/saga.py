"""Orquestador del SAGA de reserva de un paquete.

Pasos, en orden: FLIGHT -> HOTEL -> CAR -> PAYMENT (solo los ítems que trae la
orden). Cada paso tiene su compensación:

    FLIGHT / HOTEL / CAR   POST   {servicio}/reservations
        compensación       DELETE {servicio}/reservations/{order_id}
    PAYMENT                registra el cobro en orders.payments
        compensación       lo marca REFUNDED

Si un paso falla se compensan, en orden inverso, todos los pasos iniciados,
incluido el que falló: un timeout no dice si la reserva alcanzó a crearse.
Reservar y cancelar son idempotentes en cada servicio, así que repetir es seguro.

Cada transición queda en orders.saga_steps.
"""

import asyncio
import logging
import os
from decimal import Decimal
from uuid import UUID

import httpx

from .db import pool

logger = logging.getLogger("saga")

# Paso -> (URL del servicio, campo de la orden con el id del ítem)
RESERVATION_STEPS = {
    "FLIGHT": (os.environ.get("FLIGHTS_URL", "http://flights:8000"), "flight_id"),
    "HOTEL": (os.environ.get("HOTELS_URL", "http://hotels:8000"), "hotel_id"),
    "CAR": (os.environ.get("CARS_URL", "http://cars:8000"), "car_id"),
}
COMPENSATION_ATTEMPTS = 3
HTTP_TIMEOUT = httpx.Timeout(15.0)


class StepError(Exception):
    """Un paso del SAGA no pudo completarse."""


async def run(order: dict) -> None:
    """Ejecuta el SAGA de una orden recién creada (estado PENDING)."""
    steps = [step for step, (_, key) in RESERVATION_STEPS.items() if order[key]] + ["PAYMENT"]
    started: list[str] = []
    total = Decimal(0)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            for step in steps:
                started.append(step)
                await _log(order["id"], step, "EXECUTE", "STARTED")
                try:
                    if step == "PAYMENT":
                        reference = await _capture_payment(order, total)
                    else:
                        reference, price = await _reserve(client, step, order)
                        total += price
                except Exception as exc:
                    await _log(order["id"], step, "EXECUTE", "FAILED", error=str(exc))
                    raise StepError(f"{step}: {exc}") from exc
                await _log(order["id"], step, "EXECUTE", "SUCCEEDED", reference_id=reference)
        except StepError as failure:
            logger.warning("Orden %s: fallo en %s; compensando %s", order["id"], failure, started)
            await _set_status(order["id"], "COMPENSATING", failure_reason=str(failure))
            compensated = await compensate(client, order["id"], started)
            await _set_status(order["id"], "COMPENSATED" if compensated else "FAILED")
            return

    await _set_status(order["id"], "CONFIRMED", total_amount=total)


async def compensate(client: httpx.AsyncClient, order_id: UUID, steps: list[str]) -> bool:
    """Deshace los pasos en orden inverso. Devuelve False si alguna compensación falló."""
    all_ok = True
    for step in reversed(steps):
        await _log(order_id, step, "COMPENSATE", "STARTED")
        try:
            await _with_retries(lambda: _undo(client, step, order_id))
        except Exception as exc:
            all_ok = False
            logger.error("Orden %s: no se pudo compensar %s: %s", order_id, step, exc)
            await _log(order_id, step, "COMPENSATE", "FAILED", error=str(exc))
        else:
            await _log(order_id, step, "COMPENSATE", "SUCCEEDED")
    return all_ok


async def recover_interrupted() -> None:
    """Compensa órdenes que quedaron a medias porque el servicio se cayó.

    Se ejecuta al arrancar. Una orden PENDING o COMPENSATING sin cambios hace
    más de dos minutos no tiene ningún proceso atendiéndola.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            """select id from orders.orders
               where status in ('PENDING', 'COMPENSATING') and updated_at < now() - interval '2 minutes'"""
        )
        stuck = [row["id"] for row in await cur.fetchall()]

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for order_id in stuck:
            logger.warning("Orden %s quedó interrumpida; compensando", order_id)
            await _set_status(order_id, "COMPENSATING", failure_reason="SAGA interrumpido por reinicio del servicio")
            compensated = await compensate(client, order_id, [*RESERVATION_STEPS, "PAYMENT"])
            await _set_status(order_id, "COMPENSATED" if compensated else "FAILED")


async def _reserve(client: httpx.AsyncClient, step: str, order: dict) -> tuple[UUID, Decimal]:
    url, key = RESERVATION_STEPS[step]
    payload = {
        "order_id": str(order["id"]),
        key: str(order[key]),
        "simulate_failure": order["simulate_failure"] == step,
    }
    if step == "FLIGHT":
        payload["passengers"] = order["passengers"]

    response = await client.post(f"{url}/reservations", json=payload)
    if response.status_code != 201:
        raise StepError(f"HTTP {response.status_code}: {_detail(response)}")
    reservation = response.json()
    return UUID(reservation["id"]), Decimal(str(reservation["total_price"]))


async def _capture_payment(order: dict, total: Decimal) -> UUID:
    """Cobro simulado: no hay pasarela real, solo se registra el pago."""
    if order["simulate_failure"] == "PAYMENT":
        raise StepError("Pago rechazado (fallo simulado)")
    async with pool.connection() as conn:
        cur = await conn.execute(
            """insert into orders.payments (order_id, amount, currency, status)
               values (%s, %s, %s, 'CAPTURED')
               on conflict (order_id) do update set order_id = excluded.order_id
               returning id""",
            (order["id"], total, order["currency"]),
        )
        return (await cur.fetchone())["id"]


async def _undo(client: httpx.AsyncClient, step: str, order_id: UUID) -> None:
    if step == "PAYMENT":
        async with pool.connection() as conn:
            await conn.execute(
                """update orders.payments set status = 'REFUNDED', refunded_at = now()
                   where order_id = %s and status = 'CAPTURED'""",
                (order_id,),
            )
        return
    url, _ = RESERVATION_STEPS[step]
    response = await client.delete(f"{url}/reservations/{order_id}")
    if response.status_code != 204:
        raise StepError(f"HTTP {response.status_code}: {_detail(response)}")


async def _with_retries(action) -> None:
    for attempt in range(1, COMPENSATION_ATTEMPTS + 1):
        try:
            await action()
            return
        except Exception:
            if attempt == COMPENSATION_ATTEMPTS:
                raise
            await asyncio.sleep(0.5 * 2**attempt)


async def _log(order_id: UUID, step: str, action: str, status: str, reference_id: UUID | None = None, error: str | None = None) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """insert into orders.saga_steps (order_id, step, action, status, reference_id, error)
               values (%s, %s, %s, %s, %s, %s)""",
            (order_id, step, action, status, reference_id, error),
        )


async def _set_status(order_id: UUID, status: str, total_amount: Decimal | None = None, failure_reason: str | None = None) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            """update orders.orders
               set status = %s,
                   total_amount = coalesce(%s, total_amount),
                   failure_reason = coalesce(%s, failure_reason)
               where id = %s""",
            (status, total_amount, failure_reason, order_id),
        )


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text[:200]
