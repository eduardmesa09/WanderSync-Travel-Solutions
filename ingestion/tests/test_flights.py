from pathlib import Path

import pytest

from scrapers.flights import parse_flights

FIXTURE = Path(__file__).parent / "fixtures" / "kayak_flights_BOG-MDE.html"


@pytest.fixture(scope="module")
def flights():
    return parse_flights(FIXTURE.read_text(encoding="utf-8"), "2026-11-10")


def test_extrae_vuelos(flights):
    assert len(flights) >= 40


def test_campos_validos(flights):
    for f in flights:
        # Kayak incluye EOH (Olaya Herrera), el otro aeropuerto de Medellín.
        assert f.origin == "BOG" and f.destination in {"MDE", "EOH"}
        assert f.date == "2026-11-10"
        assert f.airline
        assert f.price > 0
        assert f.duration_minutes > 0
        assert f.stops >= 0
        assert len(f.departure_time) == 5 and len(f.arrival_time) == 5


def test_vuelo_conocido(flights):
    jetsmart = [f for f in flights if f.airline == "JetSMART" and f.departure_time == "06:50"]
    assert len(jetsmart) == 1
    f = jetsmart[0]
    assert (f.arrival_time, f.duration_minutes, f.stops, f.price) == ("08:02", 72, 0, 18.0)


def test_sin_duplicados(flights):
    keys = [(f.airline, f.destination, f.departure_time, f.arrival_time) for f in flights]
    assert len(keys) == len(set(keys))
