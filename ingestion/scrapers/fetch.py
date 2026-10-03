"""Descarga de páginas de Kayak con Playwright.

Cada descarga exitosa se guarda en ingestion/snapshots/ con el nombre de la
búsqueda. En modo offline se parsea el último snapshot de esa búsqueda en lugar
de ir a Kayak: es el respaldo para la demo si Kayak bloquea.
"""

import re
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


class SnapshotNotFoundError(Exception):
    """Modo offline sin un snapshot guardado para esa búsqueda."""


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
    name: str,
    wait_selector: str | None = None,
    settle_ms: int = 8_000,
    timeout_ms: int = 45_000,
    offline: bool = False,
) -> str:
    """Devuelve el HTML renderizado de la URL.

    name identifica la búsqueda (p. ej. "flights_BOG-MDE_2026-11-10") y nombra
    el snapshot. Con offline=True no se va a Kayak: se lee el último snapshot.

    Kayak sigue cargando resultados después de mostrar los primeros, por eso se
    espera settle_ms adicionales tras aparecer wait_selector.

    Lanza BlockedError si la página es una verificación anti-bot.
    """
    name = _safe_name(name)
    if offline:
        return load_latest_snapshot(name)

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
        save_snapshot(html, f"{name}-blocked")
        raise BlockedError(f"Kayak bloqueó la petición: {final_url}")

    save_snapshot(html, name)
    return html


def save_snapshot(html: str, name: str) -> Path:
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = SNAPSHOTS_DIR / f"{name}-{stamp}.html"
    path.write_text(html, encoding="utf-8", newline="")
    return path


def load_latest_snapshot(name: str) -> str:
    # El sufijo de fecha empieza por "2"; así se excluyen los "-blocked".
    candidates = sorted(SNAPSHOTS_DIR.glob(f"{_safe_name(name)}-2*.html"))
    if not candidates:
        raise SnapshotNotFoundError(f"No hay snapshot guardado para {name}")
    return candidates[-1].read_text(encoding="utf-8")


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
