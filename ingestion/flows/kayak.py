"""Flow de Prefect que orquesta el scraping de Kayak sobre el clúster de Dask.

Por cada destino se lanzan tres tareas (vuelos, hoteles, autos). Dask las
reparte entre sus workers; cada tarea descarga, parsea y guarda en Supabase
desde el propio worker. Prefect registra estados, reintentos y logs.

Uso:
    python -m flows.kayak          registra el deployment y lo ejecuta cada 6 h
    python -m flows.kayak --once   una sola ejecución, sin deployment
"""

import os
import random
import sys
import time
from datetime import date, timedelta

from prefect import flow, get_run_logger, task
from prefect_dask import DaskTaskRunner

from scrapers.cars import scrape_cars
from scrapers.flights import scrape_flights
from scrapers.hotels import scrape_hotels
from storage import connect, save_cars, save_flights, save_hotels

# Código IATA del destino -> ciudad en el formato que acepta Kayak para hoteles.
DESTINATIONS = {
    "MDE": "Medellin,Antioquia,Colombia",
    "CTG": "Cartagena,Bolivar,Colombia",
    "SMR": "Santa Marta,Magdalena,Colombia",
}

# Reintentos ante bloqueo de Kayak, timeouts o páginas sin resultados. La
# espera crece porque el bloqueo anti-bot de Kayak se levanta en minutos.
RETRY = dict(retries=3, retry_delay_seconds=[30, 90, 180], retry_jitter_factor=0.5)


class EmptyResultError(Exception):
    """La página cargó pero no tenía resultados; se trata como fallo para reintentar."""


def _pause(offline: bool) -> None:
    # Separa las peticiones de los workers para no parecer un bot.
    if not offline:
        time.sleep(random.uniform(2, 8))


@task(name="vuelos", tags=["kayak"], **RETRY)
def ingest_flights(origin: str, dest: str, departure: str, offline: bool) -> int:
    logger = get_run_logger()
    _pause(offline)
    flights = scrape_flights(origin, dest, departure, offline=offline)
    if not flights:
        raise EmptyResultError(f"Sin vuelos {origin}-{dest} {departure}")
    with connect() as conn:
        saved = save_flights(conn, flights)
    logger.info("%s vuelos %s-%s guardados (desde USD %.0f)", saved, origin, dest, min(f.price for f in flights))
    return saved


@task(name="hoteles", tags=["kayak"], **RETRY)
def ingest_hotels(dest: str, checkin: str, checkout: str, offline: bool) -> int:
    logger = get_run_logger()
    city = DESTINATIONS[dest]
    _pause(offline)
    hotels = scrape_hotels(city, checkin, checkout, destination=dest, offline=offline)
    if not hotels:
        raise EmptyResultError(f"Sin hoteles en {city} {checkin}")
    with connect() as conn:
        saved = save_hotels(conn, hotels)
    logger.info("%s hoteles en %s guardados", saved, city)
    return saved


@task(name="autos", tags=["kayak"], **RETRY)
def ingest_cars(airport: str, pickup: str, dropoff: str, offline: bool) -> int:
    logger = get_run_logger()
    _pause(offline)
    cars = scrape_cars(airport, pickup, dropoff, offline=offline)
    if not cars:
        raise EmptyResultError(f"Sin autos en {airport} {pickup}")
    with connect() as conn:
        saved = save_cars(conn, cars)
    logger.info("%s autos en %s guardados", saved, airport)
    return saved


@flow(
    name="ingesta-kayak",
    # Sin DASK_SCHEDULER_ADDRESS, prefect-dask levanta un clúster local temporal.
    task_runner=DaskTaskRunner(address=os.environ.get("DASK_SCHEDULER_ADDRESS")),
)
def kayak_ingestion(
    origin: str = "BOG",
    destinations: list[str] = list(DESTINATIONS),
    departure_date: str | None = None,
    days_ahead: int = 30,
    nights: int = 2,
    offline: bool = False,
) -> dict:
    """Ingesta de vuelos, hoteles y autos.

    departure_date (YYYY-MM-DD) tiene prioridad sobre days_ahead. Con
    offline=True se parsean los snapshots guardados en lugar de ir a Kayak;
    hay que usar fechas de una corrida anterior.
    """
    logger = get_run_logger()
    unknown = set(destinations) - DESTINATIONS.keys()
    if unknown:
        raise ValueError(f"Destinos sin configurar: {sorted(unknown)}. Válidos: {sorted(DESTINATIONS)}")

    start = date.fromisoformat(departure_date) if departure_date else date.today() + timedelta(days=days_ahead)
    end = start + timedelta(days=nights)
    logger.info("Ingesta %s -> %s, %s a %s%s", origin, destinations, start, end, " (offline)" if offline else "")

    futures = {}
    for dest in destinations:
        futures[f"vuelos {origin}-{dest}"] = ingest_flights.submit(origin, dest, start.isoformat(), offline)
        futures[f"hoteles {dest}"] = ingest_hotels.submit(dest, start.isoformat(), end.isoformat(), offline)
        futures[f"autos {dest}"] = ingest_cars.submit(dest, start.isoformat(), end.isoformat(), offline)

    summary, failed = {}, []
    for label, future in futures.items():
        future.wait()
        if future.state.is_completed():
            summary[label] = future.result()
        else:
            failed.append(label)
            summary[label] = None

    logger.info("Resumen: %s", summary)
    if failed and len(failed) == len(futures):
        raise RuntimeError(f"Fallaron todas las tareas: {failed}")
    if failed:
        logger.warning("Tareas fallidas tras agotar reintentos: %s", failed)
    return summary


if __name__ == "__main__":
    if "--once" in sys.argv:
        kayak_ingestion()
    else:
        kayak_ingestion.serve(name="kayak-cada-6h", interval=timedelta(hours=6))
