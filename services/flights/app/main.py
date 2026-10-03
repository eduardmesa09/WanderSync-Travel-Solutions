"""Microservicio de vuelos: catálogo y reservas. Solo usa el esquema flights."""

from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .db import pool

FLIGHT_COLUMNS = """id, origin, destination, departure_date, departure_time, arrival_time,
    arrival_day_offset, airline, stops, duration_minutes, price, currency, fare_class"""
RESERVATION_COLUMNS = "id, order_id, flight_id, passengers, total_price, currency, status, created_at, cancelled_at"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await pool.close()


app = FastAPI(title="Vuelos", lifespan=lifespan)


class ReservationIn(BaseModel):
    order_id: UUID
    flight_id: UUID
    passengers: int = Field(1, ge=1, le=9)
    simulate_failure: bool = False  # para la demo de compensaciones del SAGA


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/flights")
async def search_flights(
    origin: str = Query(min_length=3, max_length=3),
    destination: str = Query(min_length=3, max_length=3),
    date: date = Query(),
    limit: int = Query(20, ge=1, le=100),
):
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""select {FLIGHT_COLUMNS} from flights.flights
                where origin = %s and destination = %s and departure_date = %s
                order by price, departure_time limit %s""",
            (origin.upper(), destination.upper(), date, limit),
        )
        return await cur.fetchall()


@app.get("/flights/{flight_id}")
async def get_flight(flight_id: UUID):
    async with pool.connection() as conn:
        cur = await conn.execute(f"select {FLIGHT_COLUMNS} from flights.flights where id = %s", (flight_id,))
        flight = await cur.fetchone()
    if flight is None:
        raise HTTPException(404, "Vuelo no encontrado")
    return flight


@app.post("/reservations", status_code=201)
async def reserve(body: ReservationIn):
    """Paso del SAGA. Idempotente: repetirlo con la misma orden devuelve la misma reserva."""
    if body.simulate_failure:
        raise HTTPException(503, "Fallo simulado del servicio de vuelos")

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""insert into flights.reservations (order_id, flight_id, passengers, total_price, currency)
                select %(order_id)s, id, %(passengers)s, price * %(passengers)s, currency
                from flights.flights where id = %(flight_id)s
                on conflict (order_id) do nothing
                returning {RESERVATION_COLUMNS}""",
            body.model_dump(),
        )
        reservation = await cur.fetchone()
        if reservation is None:
            # No insertó: o el vuelo no existe, o la orden ya tenía reserva.
            cur = await conn.execute(
                f"select {RESERVATION_COLUMNS} from flights.reservations where order_id = %s", (body.order_id,)
            )
            reservation = await cur.fetchone()

    if reservation is None:
        raise HTTPException(404, "Vuelo no encontrado")
    if reservation["status"] == "CANCELLED":
        raise HTTPException(409, "La reserva de esta orden ya fue cancelada")
    return reservation


@app.delete("/reservations/{order_id}", status_code=204)
async def cancel(order_id: UUID):
    """Compensación del SAGA. Idempotente: si no hay reserva activa, no hace nada."""
    async with pool.connection() as conn:
        await conn.execute(
            """update flights.reservations set status = 'CANCELLED', cancelled_at = now()
               where order_id = %s and status = 'RESERVED'""",
            (order_id,),
        )
