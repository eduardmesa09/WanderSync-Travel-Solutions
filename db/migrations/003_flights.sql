-- Catálogo de vuelos, alimentado por la ingesta (Kayak).
create table flights.flights (
    id                 uuid primary key default gen_random_uuid(),
    origin             char(3) not null,
    destination        char(3) not null,
    departure_date     date not null,
    departure_time     time not null,
    arrival_time       time not null,
    arrival_day_offset smallint not null default 0 check (arrival_day_offset between 0 and 3),
    airline            text not null,
    stops              smallint not null check (stops >= 0),
    duration_minutes   integer not null check (duration_minutes > 0),
    price              numeric(10, 2) not null check (price > 0),  -- por pasajero
    currency           char(3) not null default 'USD',
    fare_class         text,
    provider           text,
    source             text not null default 'kayak',
    scraped_at         timestamptz not null default now(),

    -- Kayak no entrega número de vuelo; esta combinación identifica el itinerario.
    constraint flights_natural_key
        unique (origin, destination, departure_date, airline, departure_time, arrival_time)
);

create index flights_search_idx on flights.flights (origin, destination, departure_date, price);

-- Reservas creadas por el SAGA. Una por orden: reintentar el paso devuelve la misma.
create table flights.reservations (
    id           uuid primary key default gen_random_uuid(),
    order_id     uuid not null,
    flight_id    uuid not null references flights.flights (id),
    passengers   smallint not null default 1 check (passengers > 0),
    total_price  numeric(10, 2) not null check (total_price > 0),  -- congelado al reservar
    currency     char(3) not null,
    status       text not null default 'RESERVED' check (status in ('RESERVED', 'CANCELLED')),
    created_at   timestamptz not null default now(),
    cancelled_at timestamptz,

    constraint flights_reservations_order_key unique (order_id),
    constraint flights_reservations_cancelled_at check ((status = 'CANCELLED') = (cancelled_at is not null))
);
