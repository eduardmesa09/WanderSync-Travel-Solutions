from pathlib import Path

import pytest

from scrapers.cars import parse_cars

FIXTURE = Path(__file__).parent / "fixtures" / "kayak_cars_MDE.html"


@pytest.fixture(scope="module")
def cars():
    return parse_cars(FIXTURE.read_text(encoding="utf-8"), "MDE", "2026-11-10", "2026-11-12")


def test_extrae_autos(cars):
    assert len(cars) >= 10


def test_campos_validos(cars):
    for c in cars:
        assert c.kayak_id and c.category
        assert c.price_total > 0
        assert c.transmission in {"automatic", "manual", None}
        assert c.pickup_airport == "MDE"


def test_auto_conocido(cars):
    car = next(c for c in cars if c.kayak_id == "15445e4dbc80a3869f6fb2fa6a6756d8")
    assert (car.category, car.agency, car.provider, car.price_total) == ("Economy", "Alamo", "Expedia", 96.0)
    assert (car.passengers, car.bags, car.doors, car.transmission) == (4, 2, 4, "automatic")
    assert car.model == "Class Economy Car or similar"
    assert car.free_cancellation and car.air_conditioning


def test_hay_manuales_y_automaticos(cars):
    assert {"automatic", "manual"} <= {c.transmission for c in cars}
