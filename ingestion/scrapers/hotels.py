"""Parser de resultados de hoteles de Kayak.

Kayak usa clases CSS ofuscadas que cambian con el tiempo. Si el parser deja de
encontrar hoteles, revisar los selectores de este archivo contra un snapshot nuevo.
"""

import re
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup, Tag

from scrapers.fetch import fetch, hotels_url
from scrapers.parsing import is_ad, parse_float, parse_int, parse_price, text

CARD = ".S0Ps-resultInner"
NAME = "a.c9Hnq-big-name"
RATING = ".c9kNN"
REVIEWS = ".AFFP-des"
STARS = ".hEI8"
# Kayak muestra varias ofertas por hotel; se toma la más barata.
PRICES = ".Ptt7-price, .sA8G-price, .c1XBO-primary-price"
FREEBIES = ".iyw8-freebies"

DISTANCE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*mi$")


@dataclass
class Hotel:
    name: str
    city: str
    checkin: str
    checkout: str
    price_per_night: float
    currency: str
    stars: int | None
    rating: float | None  # sobre 10
    review_count: int | None
    distance_miles: float | None  # desde el punto de referencia de la búsqueda
    free_breakfast: bool
    destination: str | None = None  # código IATA del destino buscado
    source: str = "kayak"

    def to_dict(self) -> dict:
        return asdict(self)


def scrape_hotels(
    city: str, checkin: str, checkout: str, destination: str | None = None, offline: bool = False
) -> list[Hotel]:
    """Descarga y parsea hoteles. city como "Medellin,Antioquia,Colombia"."""
    html = fetch(
        hotels_url(city, checkin, checkout), f"hotels_{city}_{checkin}_{checkout}", wait_selector=CARD, offline=offline
    )
    return parse_hotels(html, city, checkin, checkout, destination)


def parse_hotels(html: str, city: str, checkin: str, checkout: str, destination: str | None = None) -> list[Hotel]:
    soup = BeautifulSoup(html, "lxml")
    hotels: dict[str, Hotel] = {}
    for card in soup.select(CARD):
        if is_ad(card):
            continue
        hotel = _parse_card(card, city, checkin, checkout)
        if hotel and (hotel.name not in hotels or hotel.price_per_night < hotels[hotel.name].price_per_night):
            hotel.destination = destination
            hotels[hotel.name] = hotel
    return list(hotels.values())


def _parse_card(card: Tag, city: str, checkin: str, checkout: str) -> Hotel | None:
    name = text(card.select_one(NAME))
    prices = [p for p in (parse_price(text(el)) for el in card.select(PRICES)) if p]
    if not name or not prices:
        return None

    stars_text = text(card.select_one(STARS))
    return Hotel(
        name=name,
        city=city,
        checkin=checkin,
        checkout=checkout,
        price_per_night=min(prices),
        currency="USD",
        stars=parse_int(stars_text) if "star" in stars_text else None,
        rating=parse_float(text(card.select_one(RATING))),
        review_count=_parse_reviews(text(card.select_one(REVIEWS))),
        distance_miles=_parse_distance(card),
        free_breakfast=any("breakfast" in text(el).lower() for el in card.select(FREEBIES)),
    )


def _parse_reviews(value: str) -> int | None:
    # "Very good (4169)"
    match = re.search(r"\(([\d,]+)\)", value)
    return int(match.group(1).replace(",", "")) if match else None


def _parse_distance(card: Tag) -> float | None:
    for strong in card.find_all("strong"):
        match = DISTANCE_RE.match(strong.get_text(strip=True))
        if match:
            return float(match.group(1))
    return None
