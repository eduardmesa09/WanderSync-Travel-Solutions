"""Parser de resultados de vuelos de Kayak (solo ida).

Kayak usa clases CSS ofuscadas que cambian con el tiempo. Si el parser deja de
encontrar vuelos, revisar los selectores de este archivo contra un snapshot nuevo.
"""

import re
from dataclasses import asdict, dataclass
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from scrapers.fetch import fetch, flights_url
from scrapers.parsing import is_ad, parse_price
from scrapers.parsing import text as _text

CARD = ".Fxw9-result-item-container"
LEG = "li.hJSA-item"
TIMES = ".vmXl-mod-variant-large"
DURATION = ".vmXl-mod-variant-default"
AIRPORTS = ".EFvI"
PRICE = ".e2GB-price-text"
FARE = ".Hy6H"
PROVIDER = ".M_JD-provider-name"

TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*[ap]m)(?:\s*\+(\d))?", re.I)
DURATION_RE = re.compile(r"(?:(\d+)h)?\s*(?:(\d+)m)?")
STOPS_RE = re.compile(r"^(nonstop|(\d+)\s+stops?)$", re.I)


@dataclass
class Flight:
    origin: str
    destination: str
    date: str
    departure_time: str  # HH:MM, 24 h
    arrival_time: str  # HH:MM, 24 h
    arrival_day_offset: int
    airline: str
    stops: int
    duration_minutes: int
    price: float
    currency: str
    fare_class: str | None
    provider: str | None
    source: str = "kayak"

    def to_dict(self) -> dict:
        return asdict(self)


def scrape_flights(origin: str, dest: str, date: str, offline: bool = False) -> list[Flight]:
    """Descarga y parsea los vuelos de ida para una ruta y fecha (YYYY-MM-DD)."""
    html = fetch(
        flights_url(origin, dest, date), f"flights_{origin}-{dest}_{date}", wait_selector=PRICE, offline=offline
    )
    return parse_flights(html, date)


def parse_flights(html: str, date: str) -> list[Flight]:
    soup = BeautifulSoup(html, "lxml")
    flights: dict[tuple, Flight] = {}
    for card in soup.select(CARD):
        if is_ad(card):
            continue
        flight = _parse_card(card, date)
        if flight is None:
            continue
        # Kayak repite el mismo vuelo en varias tarjetas (Best, Cheapest...); se deja el más barato.
        key = (flight.airline, flight.origin, flight.destination, flight.departure_time, flight.arrival_time)
        if key not in flights or flight.price < flights[key].price:
            flights[key] = flight
    return list(flights.values())


def _parse_card(card: Tag, date: str) -> Flight | None:
    legs = card.select(LEG)
    price_el = card.select_one(PRICE)
    if len(legs) != 1 or price_el is None:
        return None  # solo ida; tarjetas sin precio son banners
    leg = legs[0]

    times = TIME_RE.findall(_text(leg.select_one(TIMES)))
    airports = [a.strip() for a in _text(leg.select_one(AIRPORTS)).split("-")]
    airline_img = leg.find("img", alt=True)
    stops = _parse_stops(leg)
    # La misma clase envuelve la duración y el texto de escalas; se toma la que parsea.
    duration = next(
        (d for d in (_parse_duration(_text(el)) for el in leg.select(DURATION)) if d), None
    )
    price = parse_price(_text(price_el))
    if len(times) != 2 or len(airports) != 2 or not airline_img or stops is None or not duration or price is None:
        return None

    return Flight(
        origin=airports[0],
        destination=airports[1],
        date=date,
        departure_time=_to_24h(times[0][0]),
        arrival_time=_to_24h(times[1][0]),
        arrival_day_offset=int(times[1][1] or 0),
        airline=airline_img["alt"].strip(),
        stops=stops,
        duration_minutes=duration,
        price=price,
        currency="USD",
        fare_class=_text(card.select_one(FARE)) or None,
        provider=_text(card.select_one(PROVIDER)) or None,
    )


def _parse_stops(leg: Tag) -> int | None:
    for span in leg.find_all("span"):
        match = STOPS_RE.match(span.get_text(strip=True))
        if match:
            return 0 if match.group(2) is None else int(match.group(2))
    return None


def _parse_duration(text: str) -> int | None:
    match = DURATION_RE.fullmatch(text.strip())
    if not match or not any(match.groups()):
        return None
    hours, minutes = (int(g or 0) for g in match.groups())
    return hours * 60 + minutes


def _to_24h(value: str) -> str:
    return datetime.strptime(value.replace(" ", "").lower(), "%I:%M%p").strftime("%H:%M")
