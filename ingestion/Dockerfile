# Una sola imagen para el scheduler de Dask, los workers y el proceso del flow:
# Dask y Prefect fallan si cliente y workers tienen versiones distintas.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY scrapers/ scrapers/
COPY flows/ flows/
COPY storage.py .

# Páginas reales de Kayak como snapshots iniciales: el modo offline funciona
# desde el primer arranque con destino MDE y fecha 2026-11-10.
COPY tests/fixtures/kayak_flights_BOG-MDE.html snapshots/flights_BOG-MDE_2026-11-10-20261003T000000Z.html
COPY tests/fixtures/kayak_hotels_MDE.html snapshots/hotels_Medellin_Antioquia_Colombia_2026-11-10_2026-11-12-20261003T000000Z.html
COPY tests/fixtures/kayak_cars_MDE.html snapshots/cars_MDE_2026-11-10_2026-11-12-20261003T000000Z.html

RUN useradd --create-home app && chown -R app /app
USER app

CMD ["python", "-m", "flows.kayak"]
