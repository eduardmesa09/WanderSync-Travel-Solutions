# Ingesta: scrapers de Kayak

Descargan resultados de vuelos, hoteles y autos de Kayak con Playwright y los convierten en registros limpios.

## Uso local

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # en Linux/Mac: .venv/bin/pip
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m pytest
```

```python
from scrapers.flights import scrape_flights
from scrapers.hotels import scrape_hotels
from scrapers.cars import scrape_cars

scrape_flights("BOG", "MDE", "2026-11-10")
scrape_hotels("Medellin,Antioquia,Colombia", "2026-11-10", "2026-11-12")
scrape_cars("MDE", "2026-11-10", "2026-11-12")
```

## Formatos de URL verificados

| Vertical | Formato | Nota |
|---|---|---|
| Vuelos | `/flights/BOG-MDE/2026-11-10` | Incluye todos los aeropuertos de la ciudad destino (MDE y EOH) |
| Hoteles | `/hotels/Medellin,Antioquia,Colombia/<checkin>/<checkout>/2adults` | Con `Medellin,Colombia` Kayak redirige a la portada |
| Autos | `/cars/MDE/<recogida>/<entrega>` | Con nombre de ciudad la resuelve mal; usar código IATA |

## Lo que se sabe del anti-bot

- Unas ocho peticiones seguidas bastan para que Kayak redirija todo a `/help/bots.html`. El bloqueo se levantó en pocos minutos.
- `fetch()` lanza `BlockedError` cuando detecta esa redirección. No se intenta evadir: el flow de Prefect reintenta con espera.
- Cada página descargada se guarda en `snapshots/` (ignorado por git). Los fixtures de `tests/fixtures/` son páginas reales y sirven de respaldo para la demo.

## Limitaciones conocidas

- Kayak muestra unos 50 vuelos por búsqueda; los demás requieren pulsar "Show more results".
- Precios en USD. El precio de hoteles es por noche y el de autos es el total del alquiler.
- La búsqueda de hoteles toma como referencia el aeropuerto, así que `distance_miles` es la distancia a Rionegro, no al centro.
- Las clases CSS de Kayak están ofuscadas y cambian. Si un parser devuelve cero resultados, actualizar sus selectores contra un snapshot nuevo.
