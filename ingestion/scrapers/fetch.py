"""Descarga de páginas de Kayak con Playwright.

Cada descarga exitosa se guarda en ingestion/snapshots/ para poder volver a
parsearla si Kayak bloquea durante la demo.
"""

from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.kayak.com"
SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "snapshots"

# Kayak redirige a estas rutas cuando detecta tráfico automatizado. No se busca
# "captcha" en el HTML porque aparece en scripts de páginas normales.
BLOCK_PATHS = ("/help/bots", "/security/check")


class BlockedError(Exception):
    """Kayak mostró captcha o verificación anti-bot."""


def flights_url(origin: str, dest: str, date: str) -> str:
    return f"{BASE_URL}/flights/{origin}-{dest}/{date}?sort=bestflight_a"


def hotels_url(city: str, checkin: str, checkout: str, adults: int = 2) -> str:
    """city con ciudad, región y país, p. ej. "Medellin,Antioquia,Colombia".

    "Medellin,Colombia" no basta: Kayak lo resuelve mal o redirige a la portada.
    """
    return f"{BASE_URL}/hotels/{city}/{checkin}/{checkout}/{adults}adults"


def cars_url(airport: str, pickup: str, dropoff: str) -> str:
    """airport es el código IATA de recogida, p. ej. "MDE"."""
    return f"{BASE_URL}/cars/{airport}/{pickup}/{dropoff}"


def fetch(
    url: str,
    vertical: str,
    wait_selector: str | None = None,
    settle_ms: int = 8_000,
    timeout_ms: int = 45_000,
) -> str:
    """Abre la URL, espera los resultados y devuelve el HTML renderizado.

    Kayak sigue cargando resultados después de mostrar los primeros, por eso se
    espera settle_ms adicionales tras aparecer wait_selector.

    Lanza BlockedError si la página es una verificación anti-bot.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="en-US",
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                except PlaywrightTimeout:
                    pass  # se decide abajo si fue bloqueo o página vacía
            page.wait_for_timeout(settle_ms)
            html = page.content()
            final_url = page.url
        finally:
            browser.close()

    if any(path in final_url for path in BLOCK_PATHS):
        save_snapshot(html, f"{vertical}-blocked")
        raise BlockedError(f"Kayak bloqueó la petición: {final_url}")

    save_snapshot(html, vertical)
    return html


def save_snapshot(html: str, name: str) -> Path:
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SNAPSHOTS_DIR / f"{name}-{stamp}.html"
    path.write_text(html, encoding="utf-8")
    return path
