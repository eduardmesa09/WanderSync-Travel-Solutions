# WanderSync Travel Solutions

Plataforma de empaquetamiento turístico dinámico: busca y reserva vuelos, hoteles y autos como un solo paquete. Proyecto del Parcial 2 de Patrones Arquitectónicos Avanzados.

El enunciado completo está en [Parcial 2 - Sistema de Reservas Turísticas.md](Parcial%202%20-%20Sistema%20de%20Reservas%20Turísticas.md).

> **Estado:** backend completo: gateway GraphQL, microservicios y SAGA ([services/](services/README.md)), ingesta de Kayak con Prefect + Dask ([ingestion/](ingestion/README.md)) y base de datos en Supabase ([db/](db/README.md)). Frontend completo ([frontend/](frontend/README.md)). Falta el documento técnico.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React + Vite |
| API Gateway | FastAPI + Strawberry (GraphQL) |
| Microservicios | FastAPI (REST interno) |
| Base de datos | Supabase Cloud (Postgres) |
| Sesiones y rate limiting | Redis |
| Ingesta | Dask + Prefect, scraping de Kayak con Playwright |
| Observabilidad | Prefect: flows de ingesta y del SAGA (pasos y compensaciones) |
| Despliegue | Docker Compose |

## Arquitectura

```
React+Vite ──GraphQL──> Gateway ──REST──> Vuelos | Hoteles | Autos | Órdenes (SAGA)
                          │                              │
                          └─> Redis                      v
Prefect ──> Dask scheduler ──> Dask workers ──────> Supabase (Postgres)
                                    │
                                    └─scraping─> Kayak
```

- El frontend habla **solo** con el gateway, y **solo** por GraphQL.
- El gateway traduce cada operación a llamadas REST internas. Los microservicios no publican puertos fuera de Docker.
- Órdenes orquesta el SAGA: reservar vuelo → hotel → auto → cobrar → confirmar. Si un paso falla, compensa en orden inverso.
- Cada microservicio usa su propio esquema de Postgres.

## Estructura del repositorio

```
frontend/              Aplicación React + Vite
services/
  gateway/             API Gateway GraphQL, autenticación, sesiones, rate limiting
  flights/             Microservicio de vuelos
  hotels/              Microservicio de hoteles
  cars/                Microservicio de autos
  orders/              Órdenes, facturación y orquestador SAGA
ingestion/
  flows/               Flows de Prefect
  scrapers/            Un scraper por vertical (vuelos, hoteles, autos)
  snapshots/           HTML guardado de corridas exitosas (respaldo para la demo)
db/
  migrations/          Scripts SQL versionados para Supabase
docs/
  architecture/        Documento técnico y diagramas
  security/            Reportes de pip-audit y npm audit
```

## Responsables

| Área | Carpetas | Responsable |
|---|---|---|
| Backend | `services/`, `ingestion/`, `db/`, `docker-compose.yml` | _nombre_ |
| Frontend | `frontend/` | _nombre_ |

`docs/` es de ambos.

## Cómo trabajamos

- **El contrato entre ambos es el esquema GraphQL.** El gateway exporta el esquema a `services/gateway/schema.graphql`; el frontend lo usa como única referencia. Cualquier cambio en ese archivo se avisa antes de hacer merge.
- **Todo se trabaja directo en `main`.** Hagan `git pull` antes de empezar y commits pequeños para evitar conflictos.
- **Cada uno toca solo sus carpetas.** Si hace falta un cambio en el área del otro, se le pide.
- **Secretos:** las credenciales van en `.env`, que no se sube. Si se agrega una variable, se agrega también a `.env.example`.

## Puesta en marcha

1. Copiar `.env.example` a `.env` y completar las credenciales de Supabase.
2. `docker compose up --build`. La primera vez tarda: descarga Chromium y la imagen de Prefect.
   - Frontend: http://localhost:3000
   - API GraphQL (con GraphiQL): http://localhost:8000/graphql
   - Prefect: http://localhost:4200 (flow `ingesta-kayak` y una corrida de `saga-reserva` por cada reserva)
   - Dashboard de Dask: http://localhost:8787
3. Para comprobar que todo funciona: `python scripts/smoke_test.py` (requiere `pip install httpx`).

## Operaciones GraphQL

El contrato completo está en [services/gateway/schema.graphql](services/gateway/schema.graphql); ejemplos y notas para el frontend en [services/README.md](services/README.md).

| Tipo | Operación | Descripción |
|---|---|---|
| Consulta | `me` | Usuario de la sesión actual |
| Consulta | `searchPackages` | Vuelos, hoteles y autos consolidados para un destino y fechas |
| Consulta | `myBookings` | Reservas del usuario autenticado |
| Consulta | `booking(id)` | Detalle de una reserva y bitácora de su SAGA |
| Mutación | `register`, `login`, `logout` | Autenticación |
| Mutación | `bookPackage` | Checkout: reserva y cobra el paquete mediante el SAGA |
