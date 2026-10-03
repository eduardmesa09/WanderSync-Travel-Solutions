"""Microservicio de órdenes y facturación. Orquesta el SAGA. Solo usa el esquema orders."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator

from . import saga
from .db import pool

logging.basicConfig(level=logging.INFO)

ORDER_COLUMNS = """id, user_id, flight_id, hotel_id, car_id, passengers, total_amount, currency,
    status, failure_reason, simulate_failure, created_at, updated_at"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    recovery = asyncio.create_task(saga.recover_interrupted())
    yield
    recovery.cancel()
    await pool.close()


app = FastAPI(title="Órdenes", lifespan=lifespan)


class OrderIn(BaseModel):
    user_id: UUID
    flight_id: UUID | None = None
    hotel_id: UUID | None = None
    car_id: UUID | None = None
    passengers: int = Field(1, ge=1, le=9)
    idempotency_key: str = Field(min_length=8, max_length=100)
    # Paso que se fuerza a fallar para demostrar las compensaciones.
    simulate_failure: Literal["FLIGHT", "HOTEL", "CAR", "PAYMENT"] | None = None

    @model_validator(mode="after")
    def has_items(self):
        if not (self.flight_id or self.hotel_id or self.car_id):
            raise ValueError("La orden debe incluir al menos un vuelo, hotel o auto")
        return self


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
async def create_order(body: OrderIn, response: Response):
    """Crea la orden y ejecuta el SAGA. Responde cuando el SAGA terminó.

    Repetir la petición con la misma idempotency_key devuelve la orden original
    sin ejecutar nada de nuevo.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""insert into orders.orders
                    (user_id, flight_id, hotel_id, car_id, passengers, total_amount, idempotency_key, simulate_failure)
                values (%(user_id)s, %(flight_id)s, %(hotel_id)s, %(car_id)s, %(passengers)s, 0,
                        %(idempotency_key)s, %(simulate_failure)s)
                on conflict (user_id, idempotency_key) do nothing
                returning {ORDER_COLUMNS}""",
            body.model_dump(),
        )
        order = await cur.fetchone()
        if order is None:
            cur = await conn.execute(
                "select id from orders.orders where user_id = %s and idempotency_key = %s",
                (body.user_id, body.idempotency_key),
            )
            existing_id = (await cur.fetchone())["id"]

    if order is None:
        response.status_code = 200
        return await _load(existing_id, body.user_id)

    await saga.run(order)
    return await _load(order["id"], body.user_id)


@app.get("/orders")
async def list_orders(user_id: UUID = Query(), limit: int = Query(20, ge=1, le=100)):
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"select {ORDER_COLUMNS} from orders.orders where user_id = %s order by created_at desc limit %s",
            (user_id, limit),
        )
        orders = await cur.fetchall()
        # Una sola consulta para las bitácoras de todas las órdenes listadas.
        cur = await conn.execute(
            """select order_id, step, action, status, reference_id, error, created_at
               from orders.saga_steps where order_id = any(%s) order by id""",
            ([order["id"] for order in orders],),
        )
        steps = await cur.fetchall()
    for order in orders:
        order["steps"] = [step for step in steps if step["order_id"] == order["id"]]
    return orders


@app.get("/orders/{order_id}")
async def get_order(order_id: UUID, user_id: UUID = Query()):
    """Devuelve la orden con su bitácora del SAGA. user_id impide leer órdenes ajenas."""
    return await _load(order_id, user_id)


async def _load(order_id: UUID, user_id: UUID) -> dict:
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"select {ORDER_COLUMNS} from orders.orders where id = %s and user_id = %s", (order_id, user_id)
        )
        order = await cur.fetchone()
        if order is None:
            raise HTTPException(404, "Orden no encontrada")
        cur = await conn.execute(
            """select step, action, status, reference_id, error, created_at
               from orders.saga_steps where order_id = %s order by id""",
            (order_id,),
        )
        order["steps"] = await cur.fetchall()
    return order
