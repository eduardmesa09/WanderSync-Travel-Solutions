# Frontend

React 19 + Vite + TypeScript. Habla **solo** con el gateway y **solo** por GraphQL (POST a `/graphql`, con la cookie de sesión).

## Pantallas

| Ruta | Qué hace | Operación GraphQL |
|---|---|---|
| `/` | Portada, destinos con precio "desde" en vivo | `searchPackages` ×3 con alias, pidiendo solo el precio más bajo |
| `/buscar` | Resultados de vuelos, hoteles y autos; arma el paquete | `searchPackages` con fragments por tarjeta |
| `/checkout` | Resumen, modo demo del SAGA (`simulateFailure`) y pago | `bookPackage` |
| `/reservas/:id` | Estado de la orden, diagrama de pasos y bitácora del SAGA | `booking(id)` (consulta cada 1,5 s mientras esté `PENDING`/`COMPENSATING`) |
| `/reservas` | Reservas del usuario | `myBookings` |
| `/ingresar`, `/registro` | Autenticación | `login`, `register`, `me`, `logout` |

Las consultas están en [src/api/operations.ts](src/api/operations.ts). Cada vista pide solo los campos que pinta (sin over-fetching).

## Decisiones

- **Sesión en cookie `HttpOnly`.** El front nunca ve ni guarda un token; para saber si hay sesión consulta `me`.
- **Idempotencia del checkout.** Cada intento lleva un UUID (`idempotencyKey`). Si la petición falla por red, el reintento reutiliza la misma clave y el backend devuelve la orden original. Cambiar el paquete o el fallo simulado genera una clave nueva.
- **Respuestas parciales.** Si un microservicio está caído, la búsqueda muestra lo demás y avisa cuál no respondió.
- **Errores del gateway.** Se traducen por `extensions.code` (`RATE_LIMITED`, `UNAUTHENTICATED`, etc.).
- **Precio estimado vs. cobrado.** El front estima el total; el definitivo lo fija el SAGA con los precios congelados al reservar.
- **Pocas dependencias.** Solo React, React Router y Vite: menos superficie para la auditoría de dependencias ([docs/security/npm-audit-frontend.txt](../docs/security/npm-audit-frontend.txt)).
- **Movimiento.** Las animaciones (entrada del hero, contadores de precio, barrido de conectores, sacudida del paso que falla) siguen el vocabulario de la skill de motion graphics, implementadas en CSS. Se desactivan con `prefers-reduced-motion`.

## Desarrollo local

Requiere Node 20+ y el backend arriba (`docker compose up`).

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Vite lee `VITE_GRAPHQL_URL` del `.env` de la raíz del repositorio (`http://localhost:8000/graphql`). El gateway solo acepta CORS desde `http://localhost:5173`, por eso el puerto es fijo.

Otros comandos: `npm run build` (verifica tipos y compila a `dist/`), `npm run typecheck`, `npm audit`.

## Docker

El servicio `frontend` de `docker-compose.yml` compila la aplicación y la sirve con nginx en **http://localhost:3000**. nginx reenvía `/graphql` al gateway por la red interna, así el navegador habla con un solo origen. También agrega cabeceras de seguridad (CSP, `X-Frame-Options`, `nosniff`).

## Datos para la demo

El catálogo solo tiene las fechas que haya extraído la ingesta. Las páginas de respaldo de la imagen de ingesta son de **BOG → MDE, 10 de noviembre de 2026, 2 noches**, y esa es la búsqueda por defecto.

Las fotos son de Wikimedia Commons; los créditos y licencias están en el pie de página y en [src/lib/destinations.ts](src/lib/destinations.ts).
