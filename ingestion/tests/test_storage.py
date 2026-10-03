"""Pruebas de integración contra un Postgres con las migraciones aplicadas.

Usan TEST_DATABASE_URL (no DATABASE_URL) para no tocar Supabase por accidente.
Sin esa variable se omiten. Cada prueba corre dentro de una transacción que se
revierte al final, así que no dejan datos.
"""

import dataclasses
import os
from pathlib import Path

import psycopg
import pytest

from scrapers.cars import parse_cars
from scrapers.flights import parse_flights
from scrapers.hotels import parse_hotels
from storage import save_cars, save_flights, save_hotels

DSN = os.environ.get("TEST_DATABASE_URL")
FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL no está definida")


@pytest.fixture
def conn():
    with psycopg.connect(DSN) as conn:
        # Las transacciones de storage quedan anidadas como savepoints dentro de esta.
        conn.execute("begin")
        yield conn
        conn.rollback()


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _count(conn, table: str) -> int:
    return conn.execute(f"select count(*) from {table}").fetchone()[0]


def test_vuelos_upsert_sin_duplicar_y_actualiza_precio(conn):
    flights = parse_flights(_fixture("kayak_flights_BOG-MDE.html"), "2026-11-10")
    before = _count(conn, "flights.flights")

    assert save_flights(conn, flights) == len(flights)
    assert _count(conn, "flights.flights") == before + len(flights)

    cheaper = dataclasses.replace(flights[0], price=1.5)
    save_flights(conn, flights[1:] + [cheaper])
    assert _count(conn, "flights.flights") == before + len(flights)
    price = conn.execute(
        "select price from flights.flights where airline = %s and departure_date = %s and departure_time = %s",
        (cheaper.airline, cheaper.date, cheaper.departure_time),
    ).fetchone()[0]
    assert float(price) == 1.5


def test_hoteles_upsert(conn):
    hotels = parse_hotels(_fixture("kayak_hotels_MDE.html"), "Medellin,Antioquia,Colombia", "2026-11-10", "2026-11-12")
    before = _count(conn, "hotels.hotels")
    save_hotels(conn, hotels)
    save_hotels(conn, hotels)
    assert _count(conn, "hotels.hotels") == before + len(hotels)


def test_autos_upsert(conn):
    cars = parse_cars(_fixture("kayak_cars_MDE.html"), "MDE", "2026-11-10", "2026-11-12")
    before = _count(conn, "cars.cars")
    save_cars(conn, cars)
    save_cars(conn, cars)
    assert _count(conn, "cars.cars") == before + len(cars)


def test_lista_vacia_no_toca_la_base(conn):
    assert save_flights(conn, []) == 0
