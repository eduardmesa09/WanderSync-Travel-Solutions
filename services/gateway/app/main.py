"""API Gateway: único punto de entrada del frontend, todo por GraphQL en /graphql."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from strawberry.fastapi import GraphQLRouter

from . import clients, security
from .db import pool
from .schema import schema

FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
# Límite general por IP sobre todo /graphql, contra abuso y denegación de servicio.
# Las operaciones sensibles (login, registro, checkout) tienen además su propio límite.
GLOBAL_LIMIT, GLOBAL_WINDOW = 120, 60


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    yield
    await clients.http.aclose()
    await security.store.aclose()
    await pool.close()


app = FastAPI(title="WanderSync Gateway", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/graphql") and request.method == "POST":
        retry_after = await security.hit("global", security.client_ip(request), GLOBAL_LIMIT, GLOBAL_WINDOW)
        if retry_after is not None:
            return JSONResponse(
                {"errors": [{"message": "Demasiadas solicitudes", "extensions": {"code": "RATE_LIMITED"}}]},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


# Registrado después del rate limit para quedar por fuera: así las respuestas
# 429 también llevan las cabeceras CORS y el navegador puede leerlas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,  # el navegador envía la cookie de sesión
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type"],
)

# Las consultas por GET se desactivan: con la cookie SameSite=Lax, un enlace en
# otro sitio podría ejecutar operaciones con la sesión de la víctima.
app.include_router(GraphQLRouter(schema, allow_queries_via_get=False), prefix="/graphql")


@app.get("/health")
async def health():
    return {"status": "ok"}
