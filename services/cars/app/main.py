"""Microservicio de autos: catálogo y reservas. Solo usa el esquema cars."""

from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .db import pool

CAR_COLUMNS = """id, category, model, agency, pickup_airport, pickup_location, pickup_date, dropoff_date,
    passengers, bags, doors, transmission, air_conditioning, free_cancellation, score, price_total, currency"""
RESERVATION_COLUMNS = "id, order_id, car_id, total_price, currency, status, created_at, cancelled_at"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await pool.close()


app = FastAPI(title="Autos", lifespan=lifespan)


class ReservationIn(BaseModel):
    order_id: UUID
    car_id: UUID
    simulate_failure: bool = False  # para la demo de compensaciones del SAGA


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/cars")
async def search_cars(
    airport: str = Query(min_length=3, max_length=3),
    pickup: date = Query(),
    dropoff: date = Query(),
    limit: int = Query(20, ge=1, le=100),
):
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""select {CAR_COLUMNS} from cars.cars
                where pickup_airport = %s and pickup_date = %s and dropoff_date = %s
                order by price_total, score desc nulls last limit %s""",
            (airport.upper(), pickup, dropoff, limit),
        )
        return await cur.fetchall()


@app.get("/cars/{car_id}")
async def get_car(car_id: UUID):
    async with pool.connection() as conn:
        cur = await conn.execute(f"select {CAR_COLUMNS} from cars.cars where id = %s", (car_id,))
        car = await cur.fetchone()
    if car is None:
        raise HTTPException(404, "Auto no encontrado")
    return car


@app.post("/reservations", status_code=201)
async def reserve(body: ReservationIn):
    """Paso del SAGA. Idempotente: repetirlo con la misma orden devuelve la misma reserva."""
    if body.simulate_failure:
        raise HTTPException(503, "Fallo simulado del servicio de autos")

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""insert into cars.reservations (order_id, car_id, total_price, currency)
                select %(order_id)s, id, price_total, currency
                from cars.cars where id = %(car_id)s
                on conflict (order_id) do nothing
                returning {RESERVATION_COLUMNS}""",
            body.model_dump(),
        )
        reservation = await cur.fetchone()
        if reservation is None:
            # No insertó: o el auto no existe, o la orden ya tenía reserva.
            cur = await conn.execute(
                f"select {RESERVATION_COLUMNS} from cars.reservations where order_id = %s", (body.order_id,)
            )
            reservation = await cur.fetchone()

    if reservation is None:
        raise HTTPException(404, "Auto no encontrado")
    if reservation["status"] == "CANCELLED":
        raise HTTPException(409, "La reserva de esta orden ya fue cancelada")
    return reservation


@app.delete("/reservations/{order_id}", status_code=204)
async def cancel(order_id: UUID):
    """Compensación del SAGA. Idempotente: si no hay reserva activa, no hace nada."""
    async with pool.connection() as conn:
        await conn.execute(
            """update cars.reservations set status = 'CANCELLED', cancelled_at = now()
               where order_id = %s and status = 'RESERVED'""",
            (order_id,),
        )
