# Base de datos

Supabase Cloud (Postgres 17). Un esquema por microservicio, sin llaves foráneas entre esquemas.

| Esquema | Dueño | Tablas |
|---|---|---|
| `identity` | Gateway | `users` |
| `flights` | Vuelos | `flights` (catálogo), `reservations` |
| `hotels` | Hoteles | `hotels` (catálogo), `reservations` |
| `cars` | Autos | `cars` (catálogo), `reservations` |
| `orders` | Órdenes | `orders`, `saga_steps` (bitácora del SAGA), `payments` |
| `meta` | Migraciones | `schema_migrations` |

Los catálogos los llena la ingesta desde Kayak; las reservas y órdenes las crea el SAGA.

## Decisiones

- **Sin llaves foráneas entre esquemas.** `orders.orders.flight_id` apunta a un vuelo, pero sin FK: si existiera, Órdenes dependería de las tablas de Vuelos y dejarían de ser servicios independientes. La consistencia entre servicios la garantiza el SAGA.
- **Una reserva por orden en cada servicio** (`unique (order_id)`). Si el orquestador reintenta un paso, el servicio devuelve la reserva existente en lugar de crear otra.
- **Una orden por clave de idempotencia** (`unique (user_id, idempotency_key)`). Un doble clic en "pagar" no crea dos órdenes.
- **Precio congelado.** La reserva guarda el precio al momento de reservar; la ingesta puede actualizar el catálogo después sin afectarla.
- **`saga_steps` solo recibe inserciones.** Cada paso deja una fila al empezar y otra al terminar; de ahí salen la demo y los diagramas de secuencia.
- **Contraseñas solo en Argon2id.** Una restricción rechaza cualquier hash que no empiece por `$argon2id$`.
- **Esquemas cerrados a la API pública de Supabase.** La migración 001 revoca el acceso de los roles `anon` y `authenticated`; solo los microservicios entran, con la cadena de conexión.

## Conexión: transaction pooler

`DATABASE_URL` debe usar el **Transaction pooler** de Supabase (puerto 6543).

| Opción | Problema |
|---|---|
| Conexión directa | Suele ser solo IPv6; Docker no la alcanza. |
| Session pooler (5432) | Admite 15 clientes en total. Con 5 servicios, 2 workers y reinicios se agota (`EMAXCONNSESSION`), y las sesiones de contenedores ya eliminados tardan en liberarse. |
| Transaction pooler (6543) | Reparte muchos clientes sobre pocas conexiones reales. Es el que se usa. |

El transaction pooler puede enviar cada transacción por una conexión distinta, y eso impone dos reglas en el código:
- **Sin sentencias preparadas:** todas las conexiones se abren con `prepare_threshold=None`.
- **Sin estado de sesión:** el candado de las migraciones es de transacción (`pg_advisory_xact_lock`), no de sesión.

## Migraciones

Los archivos de `migrations/` se aplican en orden, una sola vez cada uno, y todas las pendientes en una sola transacción: si una falla, no se aplica ninguna. **Nunca edites una migración ya aplicada**: el script lo detecta por checksum y se detiene. Para cambiar algo, crea un archivo nuevo con el siguiente número.

```bash
# Con Docker (lee DATABASE_URL de .env)
docker compose run --rm migrate

# Sin Docker
pip install -r db/requirements.txt
DATABASE_URL=postgresql://... python db/migrate.py
```

## Probar contra un Postgres local

Las pruebas de `ingestion/tests/test_storage.py` usan `TEST_DATABASE_URL`, nunca `DATABASE_URL`, para no escribir en Supabase por accidente.

```bash
docker run -d --name wandersync-pg-test -e POSTGRES_PASSWORD=test -p 54329:5432 postgres:17-alpine
DATABASE_URL=postgresql://postgres:test@localhost:54329/postgres python db/migrate.py
cd ingestion && TEST_DATABASE_URL=postgresql://postgres:test@localhost:54329/postgres python -m pytest
```
