"""Microservicio de hoteles: catálogo y reservas. Solo usa el esquema hotels."""

from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .db import pool

HOTEL_COLUMNS = """id, name, city, destination, checkin, checkout, price_per_night, currency,
    stars, rating, review_count, distance_miles, free_breakfast"""
RESERVATION_COLUMNS = "id, order_id, hotel_id, rooms, nights, total_price, currency, status, created_at, cancelled_at"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await pool.close()


app = FastAPI(title="Hoteles", lifespan=lifespan)


class ReservationIn(BaseModel):
    order_id: UUID
    hotel_id: UUID
    rooms: int = Field(1, ge=1, le=5)
    simulate_failure: bool = False  # para la demo de compensaciones del SAGA


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/hotels")
async def search_hotels(
    destination: str = Query(min_length=3, max_length=3),
    checkin: date = Query(),
    checkout: date = Query(),
    limit: int = Query(20, ge=1, le=100),
):
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""select {HOTEL_COLUMNS} from hotels.hotels
                where destination = %s and checkin = %s and checkout = %s
                order by price_per_night, rating desc nulls last limit %s""",
            (destination.upper(), checkin, checkout, limit),
        )
        return await cur.fetchall()


@app.get("/hotels/{hotel_id}")
async def get_hotel(hotel_id: UUID):
    async with pool.connection() as conn:
        cur = await conn.execute(f"select {HOTEL_COLUMNS} from hotels.hotels where id = %s", (hotel_id,))
        hotel = await cur.fetchone()
    if hotel is None:
        raise HTTPException(404, "Hotel no encontrado")
    return hotel


@app.post("/reservations", status_code=201)
async def reserve(body: ReservationIn):
    """Paso del SAGA. Idempotente: repetirlo con la misma orden devuelve la misma reserva."""
    if body.simulate_failure:
        raise HTTPException(503, "Fallo simulado del servicio de hoteles")

    async with pool.connection() as conn:
        cur = await conn.execute(
            f"""insert into hotels.reservations (order_id, hotel_id, rooms, nights, total_price, currency)
                select %(order_id)s, id, %(rooms)s, checkout - checkin,
                       price_per_night * (checkout - checkin) * %(rooms)s, currency
                from hotels.hotels where id = %(hotel_id)s
                on conflict (order_id) do nothing
                returning {RESERVATION_COLUMNS}""",
            body.model_dump(),
        )
        reservation = await cur.fetchone()
        if reservation is None:
            # No insertó: o el hotel no existe, o la orden ya tenía reserva.
            cur = await conn.execute(
                f"select {RESERVATION_COLUMNS} from hotels.reservations where order_id = %s", (body.order_id,)
            )
            reservation = await cur.fetchone()

    if reservation is None:
        raise HTTPException(404, "Hotel no encontrado")
    if reservation["status"] == "CANCELLED":
        raise HTTPException(409, "La reserva de esta orden ya fue cancelada")
    return reservation


@app.delete("/reservations/{order_id}", status_code=204)
async def cancel(order_id: UUID):
    """Compensación del SAGA. Idempotente: si no hay reserva activa, no hace nada."""
    async with pool.connection() as conn:
        await conn.execute(
            """update hotels.reservations set status = 'CANCELLED', cancelled_at = now()
               where order_id = %s and status = 'RESERVED'""",
            (order_id,),
        )
