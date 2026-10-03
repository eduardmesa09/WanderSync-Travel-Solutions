"""Parser de resultados de alquiler de autos de Kayak.

Kayak usa clases CSS ofuscadas que cambian con el tiempo. Si el parser deja de
encontrar autos, revisar los selectores de este archivo contra un snapshot nuevo.
"""

from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup, Tag

from scrapers.fetch import cars_url, fetch
from scrapers.parsing import is_ad, parse_float, parse_int, parse_price, text

CARD = ".jo6g-car-result-item"
CATEGORY = ".MseY-title"
IMAGE = "img.js-image"
OPTION = ".WgbO-car-option"
AGENCY = "img.mR2O-agency-logo"
PICKUP = ".NYO--first-row"
SCORE = ".krwN"
PRICE = ".c4nz8-price-total"
PROVIDER = ".EuxN-provider-name"

TRANSMISSIONS = {"A": "automatic", "M": "manual"}


@dataclass
class Car:
    kayak_id: str
    category: str
    model: str | None
    agency: str | None
    pickup_airport: str
    pickup_location: str | None
    pickup_date: str
    dropoff_date: str
    passengers: int | None
    bags: int | None
    doors: int | None
    transmission: str | None
    air_conditioning: bool
    free_cancellation: bool
    score: float | None  # sobre 10
    price_total: float
    currency: str
    provider: str | None
    source: str = "kayak"

    def to_dict(self) -> dict:
        return asdict(self)


def scrape_cars(airport: str, pickup: str, dropoff: str, offline: bool = False) -> list[Car]:
    """Descarga y parsea autos para un aeropuerto (código IATA) y fechas."""
    html = fetch(
        cars_url(airport, pickup, dropoff), f"cars_{airport}_{pickup}_{dropoff}", wait_selector=CARD, offline=offline
    )
    return parse_cars(html, airport, pickup, dropoff)


def parse_cars(html: str, airport: str, pickup: str, dropoff: str) -> list[Car]:
    soup = BeautifulSoup(html, "lxml")
    cars: dict[str, Car] = {}
    for card in soup.select(CARD):
        if is_ad(card):
            continue
        car = _parse_card(card, airport, pickup, dropoff)
        if car:
            cars[car.kayak_id] = car
    return list(cars.values())


def _parse_card(card: Tag, airport: str, pickup: str, dropoff: str) -> Car | None:
    kayak_id = card.get("data-result-id")
    category = text(card.select_one(CATEGORY))
    price = parse_price(text(card.select_one(PRICE)))
    if not kayak_id or not category or price is None:
        return None

    options = {el.get("aria-label", ""): text(el) for el in card.select(OPTION)}
    agency_img = card.select_one(AGENCY)
    return Car(
        kayak_id=kayak_id,
        category=category,
        model=_parse_model(card.select_one(IMAGE)),
        agency=agency_img["alt"].removeprefix("Car agency:").strip() if agency_img and agency_img.get("alt") else None,
        pickup_airport=airport,
        pickup_location=text(card.select_one(PICKUP)) or None,
        pickup_date=pickup,
        dropoff_date=dropoff,
        passengers=parse_int(options.get("Passengers count", "")),
        bags=parse_int(options.get("Bags count", "")),
        doors=parse_int(options.get("Door count", "")),
        transmission=TRANSMISSIONS.get(options.get("Transmission type", "").strip()),
        air_conditioning="Air conditioning" in options,
        free_cancellation=any(s.get_text(strip=True).startswith("Free cancellation") for s in card.find_all("span")),
        score=parse_float(text(card.select_one(SCORE))),
        price_total=price,
        currency="USD",
        provider=text(card.select_one(PROVIDER)) or None,
    )


def _parse_model(img: Tag | None) -> str | None:
    # alt="Vehicle type: Economy - Class Economy Car or similar"
    alt = img.get("alt", "") if img else ""
    return alt.split(" - ", 1)[1].strip() if " - " in alt else None
