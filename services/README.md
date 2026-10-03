# Backend: gateway y microservicios

Cinco servicios FastAPI. El frontend solo ve el gateway; los demás no publican puertos.

| Servicio | Esquema de BD | Qué hace |
|---|---|---|
| `gateway` | `identity` | API GraphQL, autenticación, sesiones y rate limiting |
| `flights` | `flights` | Catálogo de vuelos y reservas |
| `hotels` | `hotels` | Catálogo de hoteles y reservas |
| `cars` | `cars` | Catálogo de autos y reservas |
| `orders` | `orders` | Órdenes, pago simulado y orquestador del SAGA |

## GraphQL (frontend → gateway)

Endpoint: `http://localhost:8000/graphql`. Al abrirlo en el navegador aparece GraphiQL para probar consultas.

El contrato completo está en [gateway/schema.graphql](gateway/schema.graphql). Se regenera con `python export_schema.py` desde `services/gateway` cada vez que cambie [gateway/app/schema.py](gateway/app/schema.py).

```graphql
query {
  searchPackages(destination: "MDE", departureDate: "2026-11-10", nights: 2) {
    flights(limit: 5) { id airline departureTime price }
    hotels(limit: 5) { id name pricePerNight stars }
    cars(limit: 5) { id category agency priceTotal }
  }
}

mutation {
  bookPackage(input: {
    flightId: "...", hotelId: "...", carId: "...",
    idempotencyKey: "uuid-generado-al-abrir-el-checkout",
    simulateFailure: CAR   # solo para la demo; quitar para el camino feliz
  }) {
    id status totalAmount failureReason
    steps { step action status error }
  }
}
```

Para el frontend:

- **La sesión va en una cookie `HttpOnly`.** El cliente GraphQL debe enviar credenciales (`credentials: "include"`). No hay token que guardar.
- **Solo POST.** Las consultas por GET están desactivadas.
- **Sin over-fetching.** `flights`, `hotels` y `cars` son resolvers independientes: el gateway solo llama a los servicios cuyos campos se piden, y en paralelo. Si un servicio está caído, su lista llega `null` con un error y las demás sí llegan.
- **Errores.** Cada error trae `extensions.code`: `UNAUTHENTICATED`, `BAD_USER_INPUT`, `RATE_LIMITED` (con `retryAfter` en segundos), `NOT_FOUND`, `SERVICE_UNAVAILABLE` o `SERVICE_ERROR`.
- **`idempotencyKey`.** Generar un UUID al abrir el checkout y reutilizarlo si el usuario reintenta; así un doble clic no crea dos reservas.

## REST interno (gateway y órdenes → servicios)

| Servicio | Endpoints |
|---|---|
| `flights` | `GET /flights?origin=&destination=&date=`, `GET /flights/{id}` |
| `hotels` | `GET /hotels?destination=&checkin=&checkout=`, `GET /hotels/{id}` |
| `cars` | `GET /cars?airport=&pickup=&dropoff=`, `GET /cars/{id}` |
| los tres | `POST /reservations` (reservar), `DELETE /reservations/{order_id}` (compensar) |
| `orders` | `POST /orders` (ejecuta el SAGA), `GET /orders?user_id=`, `GET /orders/{id}?user_id=` |

## SAGA (orquestación)

El orquestador está en [orders/app/saga.py](orders/app/saga.py). `bookPackage` responde cuando el SAGA terminó.

```
FLIGHT → HOTEL → CAR → PAYMENT → orden CONFIRMED
```

Si un paso falla, la orden pasa a `COMPENSATING` y se deshacen en orden inverso todos los pasos iniciados; al terminar queda `COMPENSATED`. Si una compensación falla tras 3 intentos, queda `FAILED` para revisión manual.

- **Se compensa también el paso que falló.** Un timeout no dice si la reserva alcanzó a crearse; cancelar es inofensivo si no existe.
- **Reservar y cancelar son idempotentes** (una reserva por orden en cada servicio), así que reintentar es seguro.
- **Cada transición queda en `orders.saga_steps`**, visible en el campo `steps` de la reserva.
- **Recuperación tras caídas.** Al arrancar, `orders` compensa las órdenes que quedaron `PENDING` o `COMPENSATING` hace más de dos minutos.
- **Fallo simulado.** `simulateFailure: FLIGHT | HOTEL | CAR | PAYMENT` hace que ese paso falle.

### El SAGA en Prefect

Cada reserva es una corrida del flow `saga-reserva` en Prefect (http://localhost:4200 → *Runs*), con nombre `orden-<id>`. Cada paso y cada compensación es una tarea:

```
Camino feliz        reservar-vuelo → reservar-hotel → reservar-auto → cobrar-pago          estado: Confirmada
Falla el auto       reservar-vuelo → reservar-hotel → reservar-auto ✗
                    → compensar-auto → compensar-hotel → compensar-vuelo                   estado: Compensada
Falla el pago       ... → cobrar-pago ✗
                    → compensar-pago → compensar-auto → compensar-hotel → compensar-vuelo  estado: Compensada
```

- **La tarea que falla queda en rojo** con su error, y detrás aparecen las compensaciones en orden inverso.
- **Las compensaciones reintentan** hasta 3 veces (esperas de 1 y 2 s); los reintentos se ven en la tarea.
- **El flow corre dentro del servicio de Órdenes**, sin pasar por la cola de Prefect, así que el checkout responde en pocos segundos.
- **Las reservas no dependen de Prefect.** Antes de cada SAGA, Órdenes consulta la salud de Prefect (2 s de espera máxima); si no responde, ejecuta el mismo SAGA sin registrarlo allí. La bitácora `orders.saga_steps` se escribe siempre.
- **`saga-recuperacion`** es el flow que compensa las órdenes interrumpidas por un reinicio.

## Seguridad

| Requisito | Implementación | Dónde |
|---|---|---|
| Hashing robusto | Argon2id (64 MiB, 3 iteraciones, 4 hilos). La base rechaza hashes que no sean Argon2id. | [security.py](gateway/app/security.py), migración 002 |
| Session Fixation | Sesiones en Redis. En cada login o registro se invalida el identificador anterior y se emite uno nuevo de 256 bits. El servidor no acepta identificadores que no haya emitido. | [security.py](gateway/app/security.py) |
| Cookie de sesión | `HttpOnly`, `SameSite=Lax`, expira a las 8 h. `COOKIE_SECURE=true` la restringe a HTTPS. | [security.py](gateway/app/security.py) |
| Rate limiting | Contadores en Redis. Login: 10/min por IP y 5 cada 5 min por cuenta. Registro: 10 cada 10 min por IP. Checkout y pago: 10/min por usuario. General: 120/min por IP. | [schema.py](gateway/app/schema.py), [main.py](gateway/app/main.py) |
| Enumeración de cuentas | El login responde igual y tarda lo mismo exista o no el correo. | [schema.py](gateway/app/schema.py) |
| Abuso de GraphQL | Profundidad máxima 6, máximo 10 alias, errores internos ocultos al cliente. | [schema.py](gateway/app/schema.py) |
| Superficie | Solo el gateway publica puerto. CORS limitado a `FRONTEND_ORIGINS`. | [docker-compose.yml](../docker-compose.yml) |
| Cadena de suministro | Versiones fijadas y auditadas con `pip-audit`. | [docs/security/](../docs/security/) |

Limitación conocida: detrás de Docker en local, todas las peticiones del navegador llegan con la misma IP, así que los límites por IP se comparten entre usuarios de la misma máquina.

## Prueba de punta a punta

Con el stack arriba y datos en el catálogo:

```bash
pip install httpx
python scripts/smoke_test.py
```

Recorre búsqueda, SAGA exitoso, tres fallos simulados con sus compensaciones, idempotencia, regeneración de sesión y rate limiting. Sirve como guion de la demo. Crea un usuario de prueba y cuatro órdenes en la base.
