"""Llamadas REST a los microservicios internos."""

import os

import httpx
from graphql import GraphQLError

FLIGHTS_URL = os.environ.get("FLIGHTS_URL", "http://flights:8000")
HOTELS_URL = os.environ.get("HOTELS_URL", "http://hotels:8000")
CARS_URL = os.environ.get("CARS_URL", "http://cars:8000")
ORDERS_URL = os.environ.get("ORDERS_URL", "http://orders:8000")

# El checkout espera a que termine el SAGA completo, por eso el timeout es amplio.
http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))


async def call(method: str, url: str, service: str, **kwargs) -> httpx.Response:
    """Llama a un microservicio y traduce los fallos a errores GraphQL sin detalles internos."""
    try:
        response = await http.request(method, url, **kwargs)
    except httpx.HTTPError:
        raise GraphQLError(
            f"El servicio de {service} no está disponible", extensions={"code": "SERVICE_UNAVAILABLE"}
        ) from None
    if response.status_code == 404:
        raise GraphQLError("No encontrado", extensions={"code": "NOT_FOUND"})
    if response.status_code == 422:
        raise GraphQLError("Datos inválidos", extensions={"code": "BAD_USER_INPUT"})
    if response.status_code >= 400:
        raise GraphQLError(
            f"El servicio de {service} respondió con un error", extensions={"code": "SERVICE_ERROR"}
        )
    return response
