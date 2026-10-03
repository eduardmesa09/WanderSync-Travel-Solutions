from pathlib import Path

import pytest

from scrapers.hotels import parse_hotels

FIXTURE = Path(__file__).parent / "fixtures" / "kayak_hotels_MDE.html"


@pytest.fixture(scope="module")
def hotels():
    html = FIXTURE.read_text(encoding="utf-8")
    return parse_hotels(html, "Medellin,Antioquia,Colombia", "2026-11-10", "2026-11-12")


def test_extrae_hoteles(hotels):
    assert len(hotels) >= 20


def test_campos_validos(hotels):
    for h in hotels:
        assert h.name
        assert h.price_per_night > 0
        assert h.rating is None or 0 < h.rating <= 10
        assert h.stars is None or 1 <= h.stars <= 5


def test_hotel_conocido_toma_la_oferta_mas_barata(hotels):
    dorado = next(h for h in hotels if h.name == "Hotel Dorado La 70")
    assert (dorado.price_per_night, dorado.stars, dorado.rating, dorado.review_count) == (56.0, 4, 8.5, 2419)
    assert dorado.distance_miles == 12.8
    assert dorado.free_breakfast


def test_sin_duplicados(hotels):
    names = [h.name for h in hotels]
    assert len(names) == len(set(names))
