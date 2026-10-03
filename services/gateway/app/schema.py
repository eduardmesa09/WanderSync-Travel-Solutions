"""Esquema GraphQL del gateway: el único contrato que ve el frontend."""

import dataclasses
import re
from datetime import date, timedelta
from enum import Enum
from typing import Optional

import psycopg
import strawberry
from graphql import GraphQLError
from strawberry.extensions import MaskErrors, MaxAliasesLimiter, QueryDepthLimiter
from strawberry.types import Info

from . import clients, security
from .db import pool

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128  # evita gastar CPU hasheando entradas enormes


def _build(cls, data: dict):
    """Crea un tipo GraphQL tomando de la respuesta REST solo los campos que el tipo declara."""
    return cls(**{f.name: data.get(f.name) for f in dataclasses.fields(cls) if f.init})


def _bad_input(message: str) -> GraphQLError:
    return GraphQLError(message, extensions={"code": "BAD_USER_INPUT"})


# --- Tipos -------------------------------------------------------------------

@strawberry.type
class User:
    id: strawberry.ID
    email: str
    full_name: str


@strawberry.type
class Flight:
    id: strawberry.ID
    origin: str
    destination: str
    departure_date: str
    departure_time: str
    arrival_time: str
    arrival_day_offset: int
    airline: str
    stops: int
    duration_minutes: int
    price: float = strawberry.field(description="Precio por pasajero")
    currency: str
    fare_class: Optional[str]


@strawberry.type
class Hotel:
    id: strawberry.ID
    name: str
    destination: Optional[str]
    checkin: str
    checkout: str
    price_per_night: float
    currency: str
    stars: Optional[int]
    rating: Optional[float] = strawberry.field(description="Calificación sobre 10")
    review_count: Optional[int]
    distance_miles: Optional[float] = strawberry.field(description="Distancia al aeropuerto del destino")
    free_breakfast: bool


@strawberry.type
class Car:
    id: strawberry.ID
    category: str
    model: Optional[str]
    agency: Optional[str]
    pickup_airport: str
    pickup_location: Optional[str]
    pickup_date: str
    dropoff_date: str
    passengers: Optional[int]
    bags: Optional[int]
    doors: Optional[int]
    transmission: Optional[str]
    air_conditioning: bool
    free_cancellation: bool
    score: Optional[float]
    price_total: float = strawberry.field(description="Precio total del alquiler")
    currency: str


@strawberry.type(description="Disponibilidad consolidada para armar un paquete.")
class PackageSearch:
    origin: str
    destination: str
    departure_date: str
    return_date: str

    # Cada lista es un resolver aparte: el gateway solo llama a los
    # microservicios cuyos campos pidió el cliente, y lo hace en paralelo.
    # Si un servicio está caído, su lista llega null con un error y las demás sí llegan.
    @strawberry.field
    async def flights(self, limit: int = 20) -> Optional[list[Flight]]:
        response = await clients.call(
            "GET",
            f"{clients.FLIGHTS_URL}/flights",
            "vuelos",
            params={"origin": self.origin, "destination": self.destination, "date": self.departure_date, "limit": limit},
        )
        return [_build(Flight, row) for row in response.json()]

    @strawberry.field
    async def hotels(self, limit: int = 20) -> Optional[list[Hotel]]:
        response = await clients.call(
            "GET",
            f"{clients.HOTELS_URL}/hotels",
            "hoteles",
            params={"destination": self.destination, "checkin": self.departure_date, "checkout": self.return_date, "limit": limit},
        )
        return [_build(Hotel, row) for row in response.json()]

    @strawberry.field
    async def cars(self, limit: int = 20) -> Optional[list[Car]]:
        response = await clients.call(
            "GET",
            f"{clients.CARS_URL}/cars",
            "autos",
            params={"airport": self.destination, "pickup": self.departure_date, "dropoff": self.return_date, "limit": limit},
        )
        return [_build(Car, row) for row in response.json()]


@strawberry.enum
class SagaStepName(Enum):
    FLIGHT = "FLIGHT"
    HOTEL = "HOTEL"
    CAR = "CAR"
    PAYMENT = "PAYMENT"


@strawberry.enum
class BookingStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"


@strawberry.type(description="Una transición registrada en la bitácora del SAGA.")
class SagaStep:
    step: SagaStepName
    action: str = strawberry.field(description="EXECUTE o COMPENSATE")
    status: str = strawberry.field(description="STARTED, SUCCEEDED o FAILED")
    error: Optional[str]
    created_at: str


@strawberry.type
class Booking:
    id: strawberry.ID
    status: BookingStatus
    flight_id: Optional[strawberry.ID]
    hotel_id: Optional[strawberry.ID]
    car_id: Optional[strawberry.ID]
    passengers: int
    total_amount: float
    currency: str
    failure_reason: Optional[str]
    created_at: str
    steps: list[SagaStep]


def _booking(order: dict) -> Booking:
    data = {**order, "status": BookingStatus(order["status"])}
    data["steps"] = [
        SagaStep(
            step=SagaStepName(s["step"]),
            action=s["action"],
            status=s["status"],
            error=s["error"],
            created_at=s["created_at"],
        )
        for s in order.get("steps", [])
    ]
    return _build(Booking, data)


@strawberry.input
class BookPackageInput:
    flight_id: Optional[strawberry.ID] = None
    hotel_id: Optional[strawberry.ID] = None
    car_id: Optional[strawberry.ID] = None
    passengers: int = 1
    idempotency_key: str = strawberry.field(
        description="Identificador único del intento de compra (p. ej. un UUID generado al abrir el checkout). "
        "Repetir la mutación con la misma clave devuelve la reserva original."
    )
    simulate_failure: Optional[SagaStepName] = strawberry.field(
        default=None, description="Solo para la demo: fuerza el fallo de ese paso para ver las compensaciones."
    )


# --- Consultas ---------------------------------------------------------------

@strawberry.type
class Query:
    @strawberry.field(description="Usuario de la sesión actual, o null si no hay sesión.")
    async def me(self, info: Info) -> Optional[User]:
        user_id = await security.current_user_id(info.context["request"])
        if user_id is None:
            return None
        async with pool.connection() as conn:
            cur = await conn.execute("select id, email, full_name from identity.users where id = %s", (user_id,))
            row = await cur.fetchone()
        return _build(User, row) if row else None

    @strawberry.field(description="Vuelos, hoteles y autos disponibles para un destino y fechas.")
    async def search_packages(
        self, destination: str, departure_date: date, nights: int = 2, origin: str = "BOG"
    ) -> PackageSearch:
        if not (len(origin) == len(destination) == 3 and origin.isalpha() and destination.isalpha()):
            raise _bad_input("origin y destination deben ser códigos IATA de 3 letras")
        if not 1 <= nights <= 30:
            raise _bad_input("nights debe estar entre 1 y 30")
        return PackageSearch(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date.isoformat(),
            return_date=(departure_date + timedelta(days=nights)).isoformat(),
        )

    @strawberry.field(description="Reservas del usuario autenticado, de la más reciente a la más antigua.")
    async def my_bookings(self, info: Info, limit: int = 20) -> list[Booking]:
        user_id = await security.require_user_id(info.context["request"])
        response = await clients.call(
            "GET", f"{clients.ORDERS_URL}/orders", "órdenes", params={"user_id": user_id, "limit": min(max(limit, 1), 100)}
        )
        return [_booking(order) for order in response.json()]

    @strawberry.field(description="Una reserva del usuario autenticado, con la bitácora de su SAGA.")
    async def booking(self, info: Info, id: strawberry.ID) -> Optional[Booking]:
        user_id = await security.require_user_id(info.context["request"])
        try:
            response = await clients.call(
                "GET", f"{clients.ORDERS_URL}/orders/{id}", "órdenes", params={"user_id": user_id}
            )
        except GraphQLError as error:
            if (error.extensions or {}).get("code") in ("NOT_FOUND", "BAD_USER_INPUT"):
                return None
            raise
        return _booking(response.json())


# --- Mutaciones --------------------------------------------------------------

@strawberry.type
class Mutation:
    @strawberry.mutation(description="Crea una cuenta e inicia sesión.")
    async def register(self, info: Info, email: str, password: str, full_name: str) -> User:
        request, response = info.context["request"], info.context["response"]
        await security.enforce("register", security.client_ip(request), limit=10, window=600)

        email, full_name = email.strip().lower(), full_name.strip()
        if not EMAIL_RE.match(email) or len(email) > 254:
            raise _bad_input("Correo inválido")
        if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
            raise _bad_input(f"La contraseña debe tener entre {MIN_PASSWORD_LENGTH} y {MAX_PASSWORD_LENGTH} caracteres")
        if not 1 <= len(full_name) <= 100:
            raise _bad_input("Nombre inválido")

        password_hash = await security.hash_password(password)
        try:
            async with pool.connection() as conn:
                cur = await conn.execute(
                    """insert into identity.users (email, password_hash, full_name)
                       values (%s, %s, %s) returning id, email, full_name""",
                    (email, password_hash, full_name),
                )
                row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            raise _bad_input("Ya existe una cuenta con ese correo") from None

        await security.start_session(request, response, str(row["id"]))
        return _build(User, row)

    @strawberry.mutation(description="Inicia sesión. La sesión viaja en una cookie HttpOnly.")
    async def login(self, info: Info, email: str, password: str) -> User:
        request, response = info.context["request"], info.context["response"]
        email = email.strip().lower()
        # Dos límites: por IP (un atacante probando muchas cuentas) y por
        # cuenta (muchas IP probando contraseñas de una misma cuenta).
        await security.enforce("login:ip", security.client_ip(request), limit=10, window=60)
        await security.enforce("login:email", email[:254], limit=5, window=300)

        async with pool.connection() as conn:
            cur = await conn.execute(
                "select id, email, full_name, password_hash from identity.users where lower(email) = %s", (email,)
            )
            row = await cur.fetchone()

        valid = await security.verify_password(row["password_hash"] if row else None, password[:MAX_PASSWORD_LENGTH])
        if not valid:
            # Mismo mensaje exista o no la cuenta, para no revelar qué correos están registrados.
            raise GraphQLError("Correo o contraseña incorrectos", extensions={"code": "UNAUTHENTICATED"})

        await security.start_session(request, response, str(row["id"]))
        return _build(User, row)

    @strawberry.mutation(description="Cierra la sesión actual.")
    async def logout(self, info: Info) -> bool:
        await security.end_session(info.context["request"], info.context["response"])
        return True

    @strawberry.mutation(description="Checkout: reserva el paquete y lo cobra mediante el SAGA.")
    async def book_package(self, info: Info, input: BookPackageInput) -> Booking:
        user_id = await security.require_user_id(info.context["request"])
        await security.enforce("checkout", user_id, limit=10, window=60)

        if not (input.flight_id or input.hotel_id or input.car_id):
            raise _bad_input("Elige al menos un vuelo, un hotel o un auto")
        response = await clients.call(
            "POST",
            f"{clients.ORDERS_URL}/orders",
            "órdenes",
            json={
                "user_id": user_id,
                "flight_id": input.flight_id,
                "hotel_id": input.hotel_id,
                "car_id": input.car_id,
                "passengers": input.passengers,
                "idempotency_key": input.idempotency_key,
                "simulate_failure": input.simulate_failure.value if input.simulate_failure else None,
            },
        )
        return _booking(response.json())


def _should_mask(error: GraphQLError) -> bool:
    # Los GraphQLError lanzados a propósito no traen excepción original; cualquier
    # otra excepción (un bug, un fallo de base de datos) se oculta al cliente.
    return error.original_error is not None and not isinstance(error.original_error, GraphQLError)


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[
        QueryDepthLimiter(max_depth=6),
        MaxAliasesLimiter(max_alias_count=10),
        MaskErrors(should_mask_error=_should_mask, error_message="Error interno"),
    ],
)
