"""Persistencia de los resultados del scraping en Supabase (Postgres).

Cada función hace upsert: si el registro ya existe (misma llave natural), se
actualizan precio y demás datos y se renueva scraped_at. Así una ingesta
repetida no duplica filas y el catálogo refleja el último precio visto.
"""

import os
from dataclasses import asdict

import psycopg

from scrapers.cars import Car
from scrapers.flights import Flight
from scrapers.hotels import Hotel

UPSERT_FLIGHTS = """
insert into flights.flights (
    origin, destination, departure_date, departure_time, arrival_time, arrival_day_offset,
    airline, stops, duration_minutes, price, currency, fare_class, provider, source, scraped_at
) values (
    %(origin)s, %(destination)s, %(date)s, %(departure_time)s, %(arrival_time)s, %(arrival_day_offset)s,
    %(airline)s, %(stops)s, %(duration_minutes)s, %(price)s, %(currency)s, %(fare_class)s, %(provider)s,
    %(source)s, now()
)
on conflict on constraint flights_natural_key do update set
    arrival_day_offset = excluded.arrival_day_offset,
    stops = excluded.stops,
    duration_minutes = excluded.duration_minutes,
    price = excluded.price,
    currency = excluded.currency,
    fare_class = excluded.fare_class,
    provider = excluded.provider,
    scraped_at = excluded.scraped_at
"""

UPSERT_HOTELS = """
insert into hotels.hotels (
    name, city, destination, checkin, checkout, price_per_night, currency, stars, rating, review_count,
    distance_miles, free_breakfast, source, scraped_at
) values (
    %(name)s, %(city)s, %(destination)s, %(checkin)s, %(checkout)s, %(price_per_night)s, %(currency)s,
    %(stars)s, %(rating)s, %(review_count)s, %(distance_miles)s, %(free_breakfast)s, %(source)s, now()
)
on conflict on constraint hotels_natural_key do update set
    destination = coalesce(excluded.destination, hotels.hotels.destination),
    price_per_night = excluded.price_per_night,
    currency = excluded.currency,
    stars = excluded.stars,
    rating = excluded.rating,
    review_count = excluded.review_count,
    distance_miles = excluded.distance_miles,
    free_breakfast = excluded.free_breakfast,
    scraped_at = excluded.scraped_at
"""

UPSERT_CARS = """
insert into cars.cars (
    kayak_id, category, model, agency, pickup_airport, pickup_location, pickup_date, dropoff_date,
    passengers, bags, doors, transmission, air_conditioning, free_cancellation, score, price_total,
    currency, provider, source, scraped_at
) values (
    %(kayak_id)s, %(category)s, %(model)s, %(agency)s, %(pickup_airport)s, %(pickup_location)s,
    %(pickup_date)s, %(dropoff_date)s, %(passengers)s, %(bags)s, %(doors)s, %(transmission)s,
    %(air_conditioning)s, %(free_cancellation)s, %(score)s, %(price_total)s, %(currency)s,
    %(provider)s, %(source)s, now()
)
on conflict on constraint cars_natural_key do update set
    category = excluded.category,
    model = excluded.model,
    agency = excluded.agency,
    pickup_location = excluded.pickup_location,
    passengers = excluded.passengers,
    bags = excluded.bags,
    doors = excluded.doors,
    transmission = excluded.transmission,
    air_conditioning = excluded.air_conditioning,
    free_cancellation = excluded.free_cancellation,
    score = excluded.score,
    price_total = excluded.price_total,
    currency = excluded.currency,
    provider = excluded.provider,
    scraped_at = excluded.scraped_at
"""


def connect(dsn: str | None = None) -> psycopg.Connection:
    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("Falta la variable DATABASE_URL")
    return psycopg.connect(dsn)


def save_flights(conn: psycopg.Connection, flights: list[Flight]) -> int:
    return _upsert(conn, UPSERT_FLIGHTS, flights)


def save_hotels(conn: psycopg.Connection, hotels: list[Hotel]) -> int:
    return _upsert(conn, UPSERT_HOTELS, hotels)


def save_cars(conn: psycopg.Connection, cars: list[Car]) -> int:
    return _upsert(conn, UPSERT_CARS, cars)


def _upsert(conn: psycopg.Connection, sql: str, records: list) -> int:
    """Guarda todos los registros en una sola transacción y devuelve cuántos fueron."""
    if not records:
        return 0
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(sql, [asdict(r) for r in records])
    return len(records)
