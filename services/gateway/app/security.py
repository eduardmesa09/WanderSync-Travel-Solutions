"""Contraseñas, sesiones y rate limiting del gateway."""

import asyncio
import os
import secrets

import redis.asyncio as redis
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request, Response
from graphql import GraphQLError

SESSION_COOKIE = "wandersync_session"
SESSION_TTL = 8 * 60 * 60  # segundos; la sesión muere a las 8 h aunque haya actividad
# En producción (HTTPS) debe ser true; en la demo local se sirve por HTTP.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

store = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

# Argon2id con los parámetros por defecto de argon2-cffi (perfil de RFC 9106):
# 64 MiB de memoria, 3 iteraciones, 4 hilos. La sal aleatoria va dentro del hash.
_hasher = PasswordHasher()
# Hash de relleno: se verifica cuando el correo no existe, para que el login
# tarde lo mismo exista o no el usuario y no se puedan enumerar cuentas.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


# --- Contraseñas -------------------------------------------------------------

async def hash_password(password: str) -> str:
    # Argon2 es costoso a propósito; se ejecuta en un hilo para no bloquear el servidor.
    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    def check() -> bool:
        try:
            return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
        except (VerificationError, InvalidHashError):
            return False

    return await asyncio.to_thread(check)


# --- Sesiones ----------------------------------------------------------------

async def start_session(request: Request, response: Response, user_id: str) -> None:
    """Crea una sesión nueva tras autenticarse.

    Mitigación de Session Fixation: el identificador que traía el navegador se
    invalida y se genera uno nuevo en el servidor. Un atacante que hubiera
    plantado un identificador en la víctima se queda con uno que ya no existe.
    El servidor tampoco acepta identificadores que no haya emitido él: una
    cookie desconocida simplemente no está en Redis.
    """
    await end_session(request, response)
    session_id = secrets.token_urlsafe(32)  # 256 bits aleatorios
    await store.set(f"session:{session_id}", user_id, ex=SESSION_TTL)
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL,
        httponly=True,  # JavaScript no puede leerla (protege ante XSS)
        samesite="lax",  # no viaja en peticiones POST de otros sitios (protege ante CSRF)
        secure=COOKIE_SECURE,
        path="/",
    )


async def end_session(request: Request, response: Response) -> None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        await store.delete(f"session:{session_id}")
        response.delete_cookie(SESSION_COOKIE, path="/")


async def current_user_id(request: Request) -> str | None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    return await store.get(f"session:{session_id}")


async def require_user_id(request: Request) -> str:
    user_id = await current_user_id(request)
    if user_id is None:
        raise GraphQLError("Debes iniciar sesión", extensions={"code": "UNAUTHENTICATED"})
    return user_id


# --- Rate limiting -----------------------------------------------------------

async def hit(name: str, key: str, limit: int, window: int) -> int | None:
    """Cuenta una petición en una ventana fija de `window` segundos.

    Devuelve None si está dentro del límite, o los segundos que faltan para
    que la ventana se reinicie si lo superó.
    """
    redis_key = f"ratelimit:{name}:{key}"
    # SET NX EX crea el contador con su expiración en un solo comando; así
    # nunca queda un contador sin expiración que bloquee para siempre.
    await store.set(redis_key, 0, ex=window, nx=True)
    if await store.incr(redis_key) <= limit:
        return None
    return max(await store.ttl(redis_key), 1)


async def enforce(name: str, key: str, limit: int, window: int) -> None:
    retry_after = await hit(name, key, limit, window)
    if retry_after is not None:
        raise GraphQLError(
            f"Demasiados intentos. Intenta de nuevo en {retry_after} s.",
            extensions={"code": "RATE_LIMITED", "retryAfter": retry_after},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
