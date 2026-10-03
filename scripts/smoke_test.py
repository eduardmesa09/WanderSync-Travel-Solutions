"""Prueba de punta a punta contra el gateway, solo por GraphQL.

Requiere el stack arriba (docker compose up) y datos en el catálogo para
MDE 2026-11-10 (los que carga la ingesta en modo offline).

Uso: python scripts/smoke_test.py [http://localhost:8000/graphql]
Necesita httpx (pip install httpx).
"""

import sys
import uuid

import httpx

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/graphql"
DEST, DATE = "MDE", "2026-11-10"
failures = 0


def gql(client: httpx.Client, query: str, variables: dict | None = None) -> dict:
    return client.post(URL, json={"query": query, "variables": variables or {}}).json()


def check(label: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += not ok
    print(f"[{'OK' if ok else 'FALLO'}] {label}{' — ' + detail if detail else ''}")


def code(result: dict) -> str | None:
    errors = result.get("errors") or [{}]
    return (errors[0].get("extensions") or {}).get("code")


BOOK = """mutation($input: BookPackageInput!) { bookPackage(input: $input) {
    id status totalAmount failureReason steps { step action status error } } }"""

client = httpx.Client(timeout=90)
email = f"demo-{uuid.uuid4().hex[:8]}@wandersync.test"
password = "una-clave-larga-de-prueba"

# --- Sesión -------------------------------------------------------------------
check("sin sesión, me es null", gql(client, "{ me { id } }")["data"]["me"] is None)
check(
    "sin sesión, bookPackage se rechaza",
    code(gql(client, BOOK, {"input": {"flightId": str(uuid.uuid4()), "idempotencyKey": uuid.uuid4().hex}}))
    == "UNAUTHENTICATED",
)
check(
    "contraseña corta se rechaza",
    code(gql(client, 'mutation { register(email: "a@b.co", password: "corta", fullName: "X") { id } }'))
    == "BAD_USER_INPUT",
)

REGISTER = "mutation($e: String!, $p: String!) { register(email: $e, password: $p, fullName: \"Demo\") { id email } }"
check("registro", gql(client, REGISTER, {"e": email, "p": password})["data"]["register"]["email"] == email)
first_session = client.cookies.get("wandersync_session")
check("el registro entrega cookie de sesión", bool(first_session))
check("me devuelve el usuario", gql(client, "{ me { email } }")["data"]["me"]["email"] == email)

# --- Búsqueda -----------------------------------------------------------------
SEARCH = """query($d: String!, $date: Date!) { searchPackages(destination: $d, departureDate: $date, nights: 2) {
    flights(limit: 3) { id airline price } hotels(limit: 3) { id name pricePerNight } cars(limit: 3) { id category priceTotal } } }"""
search = gql(client, SEARCH, {"d": DEST, "date": DATE})["data"]["searchPackages"]
check(
    "búsqueda consolidada trae las tres verticales",
    all(search[k] for k in ("flights", "hotels", "cars")),
    f"{search['flights'][0]['airline']} USD {search['flights'][0]['price']}, "
    f"{search['hotels'][0]['name']} USD {search['hotels'][0]['pricePerNight']}/noche, "
    f"{search['cars'][0]['category']} USD {search['cars'][0]['priceTotal']}" if search["flights"] else "",
)
if not all(search[k] for k in ("flights", "hotels", "cars")):
    sys.exit("No hay datos de catálogo para la búsqueda de prueba; ejecuta la ingesta primero.")
items = {"flightId": search["flights"][0]["id"], "hotelId": search["hotels"][0]["id"], "carId": search["cars"][0]["id"]}

# --- SAGA: camino feliz ---------------------------------------------------------
key = uuid.uuid4().hex
ok = gql(client, BOOK, {"input": {**items, "idempotencyKey": key}})["data"]["bookPackage"]
executed = [s["step"] for s in ok["steps"] if s["action"] == "EXECUTE" and s["status"] == "SUCCEEDED"]
check("SAGA exitoso queda CONFIRMED", ok["status"] == "CONFIRMED", f"total USD {ok['totalAmount']}")
check("ejecutó FLIGHT, HOTEL, CAR y PAYMENT en orden", executed == ["FLIGHT", "HOTEL", "CAR", "PAYMENT"])

again = gql(client, BOOK, {"input": {**items, "idempotencyKey": key}})["data"]["bookPackage"]
check("repetir el checkout devuelve la misma reserva", again["id"] == ok["id"] and len(again["steps"]) == len(ok["steps"]))

# --- SAGA: compensaciones ---------------------------------------------------------
for failing, expected in [("CAR", ["CAR", "HOTEL", "FLIGHT"]), ("PAYMENT", ["PAYMENT", "CAR", "HOTEL", "FLIGHT"]), ("FLIGHT", ["FLIGHT"])]:
    result = gql(client, BOOK, {"input": {**items, "idempotencyKey": uuid.uuid4().hex, "simulateFailure": failing}})
    booking = result["data"]["bookPackage"]
    compensated = [s["step"] for s in booking["steps"] if s["action"] == "COMPENSATE" and s["status"] == "SUCCEEDED"]
    check(f"fallo en {failing} queda COMPENSATED", booking["status"] == "COMPENSATED", booking["failureReason"] or "")
    check(f"fallo en {failing} compensa {expected} en orden inverso", compensated == expected)

bookings = gql(client, "{ myBookings { id status } }")["data"]["myBookings"]
check("myBookings lista las 4 reservas", len(bookings) == 4, ", ".join(b["status"] for b in bookings))

# --- Session fixation --------------------------------------------------------------
LOGIN = "mutation($e: String!, $p: String!) { login(email: $e, password: $p) { id } }"
gql(client, LOGIN, {"e": email, "p": password})
second_session = client.cookies.get("wandersync_session")
check("el login regenera el identificador de sesión", second_session and second_session != first_session)
old = httpx.Client(cookies={"wandersync_session": first_session})
check("el identificador anterior deja de servir", gql(old, "{ me { id } }")["data"]["me"] is None)

planted = httpx.post(
    URL,
    json={"query": LOGIN, "variables": {"e": email, "p": password}},
    cookies={"wandersync_session": "id-plantado-por-atacante"},
    timeout=30,
)
check(
    "un identificador plantado no se adopta tras el login",
    planted.cookies.get("wandersync_session") not in (None, "id-plantado-por-atacante"),
)
check(
    "el identificador plantado no da acceso",
    gql(httpx.Client(cookies={"wandersync_session": "id-plantado-por-atacante"}), "{ me { id } }")["data"]["me"] is None,
)

gql(client, "mutation { logout }")
check("tras logout, la sesión no sirve", gql(httpx.Client(cookies={"wandersync_session": second_session}), "{ me { id } }")["data"]["me"] is None)

# --- Protección de superficie --------------------------------------------------------
check("las consultas por GET están desactivadas", httpx.get(URL, params={"query": "{ me { id } }"}, headers={"accept": "application/json"}).status_code >= 400)

codes = [code(gql(client, LOGIN, {"e": email, "p": "contraseña-equivocada"})) for _ in range(7)]
check("contraseña errónea da UNAUTHENTICATED", codes[0] == "UNAUTHENTICATED")
# El límite es de 5 intentos por cuenta cada 5 minutos y cuenta también los logins correctos de arriba.
check("el login se bloquea al superar 5 intentos por cuenta", codes[-1] == "RATE_LIMITED", " ".join(str(c) for c in codes))

print(f"\n{'TODO OK' if not failures else f'{failures} verificaciones fallaron'}")
sys.exit(1 if failures else 0)
