# Ingesta: Kayak → Dask → Supabase, orquestada con Prefect

El flow `ingesta-kayak` ([flows/kayak.py](flows/kayak.py)) lanza tres tareas por destino: vuelos, hoteles y autos. Dask las reparte entre sus workers; cada worker descarga la página de Kayak con Playwright, la parsea y guarda los resultados en Supabase. Prefect registra cada tarea, sus reintentos y sus logs.

```
Prefect (flow) ──submit──> Dask scheduler ──> dask-worker 1 ──> Kayak ──> Supabase
                                          └──> dask-worker 2 ──> Kayak ──> Supabase
```

## Con Docker

`docker compose up` levanta todo. Luego:

- **Prefect:** http://localhost:4200. En *Deployments* aparece `kayak-cada-6h`, que corre solo cada 6 horas. Con *Run → Custom run* se lanza a mano y se cambian parámetros.
- **Dask:** http://localhost:8787. Ahí se ven los workers y las tareas mientras corren.

Parámetros del flow:

| Parámetro | Por defecto | Uso |
|---|---|---|
| `origin` | `BOG` | Aeropuerto de salida |
| `destinations` | `["MDE", "CTG", "SMR"]` | Destinos configurados en `DESTINATIONS` |
| `departure_date` | hoy + `days_ahead` | Fecha fija `YYYY-MM-DD`; tiene prioridad sobre `days_ahead` |
| `days_ahead` / `nights` | `30` / `2` | Salida relativa a hoy y duración de la estadía |
| `offline` | `false` | Parsea los snapshots guardados en lugar de ir a Kayak |

**Respaldo para la demo:** si Kayak bloquea, lanzar el flow con `offline: true`, `destinations: ["MDE"]` y `departure_date: "2026-11-10"`. La imagen trae páginas reales de esa búsqueda. Cada corrida en línea guarda nuevas páginas en el volumen `kayak-snapshots`, así que también sirven las fechas de cualquier corrida anterior exitosa.

## Reintentos

Cada tarea reintenta hasta 3 veces, esperando 30, 90 y 180 segundos (±50 %), cuando:
- Kayak redirige a su página anti-bot (`BlockedError`);
- la página no carga a tiempo;
- la página carga sin resultados (`EmptyResultError`).

No se intenta evadir el anti-bot. Para no provocarlo, cada worker tiene un solo hilo (máximo dos navegadores a la vez) y cada tarea espera entre 2 y 8 segundos antes de pedir la página.

Si una tarea agota sus reintentos, el flow termina igual con las demás y registra cuáles fallaron; solo falla si fallan todas.

## Uso local (sin Docker)

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # en Linux/Mac: .venv/bin/pip
.venv/Scripts/python -m playwright install chromium
.venv/Scripts/python -m pytest
```

Ejecutar desde `ingestion/`, no desde la raíz: Prefect lee el `.env` del directorio actual. Sin `DASK_SCHEDULER_ADDRESS` el flow levanta un clúster de Dask temporal en la misma máquina.

```bash
DATABASE_URL=postgresql://... python -m flows.kayak --once
```

## Formatos de URL verificados

| Vertical | Formato | Nota |
|---|---|---|
| Vuelos | `/flights/BOG-MDE/2026-11-10` | Incluye todos los aeropuertos de la ciudad destino (MDE y EOH) |
| Hoteles | `/hotels/Medellin,Antioquia,Colombia/<checkin>/<checkout>/2adults` | Con `Medellin,Colombia` Kayak redirige a la portada |
| Autos | `/cars/MDE/<recogida>/<entrega>` | Con nombre de ciudad la resuelve mal; usar código IATA |

## Lo que se sabe del anti-bot

- Unas ocho peticiones seguidas bastan para que Kayak redirija todo a `/help/bots.html`. El bloqueo se levantó en pocos minutos.
- `fetch()` lanza `BlockedError` cuando detecta esa redirección y guarda la página como `<búsqueda>-blocked-<fecha>.html`.

## Limitaciones conocidas

- Kayak muestra unos 50 vuelos por búsqueda; los demás requieren pulsar "Show more results".
- Precios en USD. El precio de hoteles es por noche y el de autos es el total del alquiler.
- La búsqueda de hoteles toma como referencia el aeropuerto, así que `distance_miles` es la distancia a Rionegro, no al centro.
- Las clases CSS de Kayak están ofuscadas y cambian. Si un parser devuelve cero resultados, actualizar sus selectores contra un snapshot nuevo.
