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

Observabilidad: el SAGA se ejecuta como un flow de Prefect ("saga-reserva")
dentro de este mismo proceso. Cada paso y cada compensación es una tarea, así
que la interfaz de Prefect muestra qué paso falló y qué compensaciones corrieron.
El flow no pasa por la cola de Prefect: corre en línea y el checkout responde
cuando termina. Si el servidor de Prefect no responde, el SAGA se ejecuta igual,
solo que sin registrarse allí.

La fuente de verdad es orders.saga_steps: cada transición queda registrada ahí
con o sin Prefect.
"""

import asyncio
import logging
import os
from decimal import Decimal
from uuid import UUID

import httpx
from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE
from prefect.context import FlowRunContext
from prefect.states import Completed, Failed

from .db import pool

logger = logging.getLogger("saga")

# Paso -> (URL del servicio, campo de la orden con el id del ítem)
RESERVATION_STEPS = {
    "FLIGHT": (os.environ.get("FLIGHTS_URL", "http://flights:8000"), "flight_id"),
    "HOTEL": (os.environ.get("HOTELS_URL", "http://hotels:8000"), "hotel_id"),
    "CAR": (os.environ.get("CARS_URL", "http://cars:8000"), "car_id"),
}
# Nombres de las tareas en la interfaz de Prefect.
EXECUTE_LABELS = {"FLIGHT": "reservar-vuelo", "HOTEL": "reservar-hotel", "CAR": "reservar-auto", "PAYMENT": "cobrar-pago"}
COMPENSATE_LABELS = {
    "FLIGHT": "compensar-vuelo",
    "HOTEL": "compensar-hotel",
    "CAR": "compensar-auto",
    "PAYMENT": "compensar-pago",
}
COMPENSATION_RETRIES = 2  # 3 intentos en total
RETRY_DELAYS = [1, 2]  # segundos

PREFECT_API_URL = os.environ.get("PREFECT_API_URL")
http = httpx.AsyncClient(timeout=httpx.Timeout(15.0))


class StepError(Exception):
    """Un paso del SAGA no pudo completarse."""


# --- Puntos de entrada ---------------------------------------------------------

async def run(order_id: UUID) -> None:
    """Ejecuta el SAGA de una orden recién creada (estado PENDING)."""
    if await _prefect_available():
        await booking_saga(str(order_id), return_state=True)
    else:
        await _execute(order_id)


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

    for order_id in stuck:
        logger.warning("Orden %s quedó interrumpida; compensando", order_id)
        if await _prefect_available():
            await saga_recovery(str(order_id), return_state=True)
        else:
            await _recover(order_id)


# --- Flows de Prefect ------------------------------------------------------------

@flow(name="saga-reserva", flow_run_name="orden-{order_id}")
async def booking_saga(order_id: str):
    """SAGA de reserva: vuelo, hotel, auto y pago, con compensaciones si algo falla."""
    return _final_state(await _execute(UUID(order_id)))


@flow(name="saga-recuperacion", flow_run_name="orden-{order_id}")
async def saga_recovery(order_id: str):
    """Compensa una orden cuyo SAGA quedó interrumpido por un reinicio del servicio."""
    return _final_state(await _recover(UUID(order_id)))


def _final_state(order: dict):
    """Estado con el que queda la corrida en Prefect, según cómo terminó la orden."""
    if order["status"] == "CONFIRMED":
        return Completed(name="Confirmada", message=f"Total {order['total_amount']} {order['currency']}")
    name = "Compensada" if order["status"] == "COMPENSATED" else "Compensación fallida"
    return Failed(name=name, message=order["failure_reason"] or "")


# --- Lógica del SAGA ---------------------------------------------------------------

async def _execute(order_id: UUID) -> dict:
    order = await _load(order_id)
    steps = [step for step, (_, key) in RESERVATION_STEPS.items() if order[key]] + ["PAYMENT"]
    started: list[str] = []
    total = Decimal(0)

    try:
        for step in steps:
            started.append(step)
            await _log(order_id, step, "EXECUTE", "STARTED")
            try:
                if step == "PAYMENT":
                    reference = await _as_task(EXECUTE_LABELS[step], _capture_payment, order, total)
                else:
                    reference, price = await _as_task(EXECUTE_LABELS[step], _reserve, step, order)
                    total += price
            except Exception as exc:
                await _log(order_id, step, "EXECUTE", "FAILED", error=str(exc))
                raise StepError(f"{step}: {exc}") from exc
            await _log(order_id, step, "EXECUTE", "SUCCEEDED", reference_id=reference)
    except StepError as failure:
        _info(f"Fallo en {failure}. Compensando en orden inverso: {list(reversed(started))}")
        await _set_status(order_id, "COMPENSATING", failure_reason=str(failure))
        compensated = await _compensate(order_id, started)
        await _set_status(order_id, "COMPENSATED" if compensated else "FAILED")
        return await _load(order_id)

    await _set_status(order_id, "CONFIRMED", total_amount=total)
    _info(f"Orden confirmada por {total} {order['currency']}")
    return await _load(order_id)


async def _recover(order_id: UUID) -> dict:
    await _set_status(order_id, "COMPENSATING", failure_reason="SAGA interrumpido por reinicio del servicio")
    compensated = await _compensate(order_id, [*RESERVATION_STEPS, "PAYMENT"])
    await _set_status(order_id, "COMPENSATED" if compensated else "FAILED")
    return await _load(order_id)


async def _compensate(order_id: UUID, steps: list[str]) -> bool:
    """Deshace los pasos en orden inverso. Devuelve False si alguna compensación falló."""
    all_ok = True
    for step in reversed(steps):
        await _log(order_id, step, "COMPENSATE", "STARTED")
        try:
            await _as_task(COMPENSATE_LABELS[step], _undo, step, order_id, retries=COMPENSATION_RETRIES)
        except Exception as exc:
            all_ok = False
            logger.error("Orden %s: no se pudo compensar %s: %s", order_id, step, exc)
            await _log(order_id, step, "COMPENSATE", "FAILED", error=str(exc))
        else:
            await _log(order_id, step, "COMPENSATE", "SUCCEEDED")
    return all_ok


# --- Pasos y compensaciones ----------------------------------------------------------

async def _reserve(step: str, order: dict) -> tuple[UUID, Decimal]:
    url, key = RESERVATION_STEPS[step]
    payload = {
        "order_id": str(order["id"]),
        key: str(order[key]),
        "simulate_failure": order["simulate_failure"] == step,
    }
    if step == "FLIGHT":
        payload["passengers"] = order["passengers"]

    response = await http.post(f"{url}/reservations", json=payload)
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


async def _undo(step: str, order_id: UUID) -> None:
    if step == "PAYMENT":
        async with pool.connection() as conn:
            await conn.execute(
                """update orders.payments set status = 'REFUNDED', refunded_at = now()
                   where order_id = %s and status = 'CAPTURED'""",
                (order_id,),
            )
        return
    url, _ = RESERVATION_STEPS[step]
    response = await http.delete(f"{url}/reservations/{order_id}")
    if response.status_code != 204:
        raise StepError(f"HTTP {response.status_code}: {_detail(response)}")


# --- Prefect ---------------------------------------------------------------------------

async def _as_task(name: str, fn, *args, retries: int = 0):
    """Ejecuta fn como tarea de Prefect si hay un flow en curso; si no, directamente."""
    if FlowRunContext.get() is not None:
        prefect_task = task(
            fn, name=name, retries=retries, retry_delay_seconds=RETRY_DELAYS[:retries] or 0, cache_policy=NO_CACHE
        )
        return await prefect_task(*args)

    for attempt in range(retries + 1):
        try:
            return await fn(*args)
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(RETRY_DELAYS[attempt])


async def _prefect_available() -> bool:
    """El SAGA no debe depender de Prefect: si no responde rápido, se ejecuta sin él."""
    if not PREFECT_API_URL:
        return False
    try:
        response = await http.get(f"{PREFECT_API_URL}/health", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        logger.warning("Prefect no responde; el SAGA se ejecuta sin registrarse en Prefect")
        return False


def _info(message: str) -> None:
    """Escribe en el log de la corrida de Prefect si la hay, y siempre en el log del servicio."""
    if FlowRunContext.get() is not None:
        get_run_logger().info(message)
    else:
        logger.info(message)


# --- Persistencia -------------------------------------------------------------------------

async def _load(order_id: UUID) -> dict:
    async with pool.connection() as conn:
        cur = await conn.execute(
            """select id, flight_id, hotel_id, car_id, passengers, total_amount, currency,
                      status, failure_reason, simulate_failure
               from orders.orders where id = %s""",
            (order_id,),
        )
        return await cur.fetchone()


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
