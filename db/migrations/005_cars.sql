-- Catálogo de autos de alquiler, alimentado por la ingesta (Kayak).
create table cars.cars (
    id                uuid primary key default gen_random_uuid(),
    kayak_id          text not null,
    category          text not null,
    model             text,
    agency            text,
    pickup_airport    char(3) not null,
    pickup_location   text,
    pickup_date       date not null,
    dropoff_date      date not null,
    passengers        smallint check (passengers > 0),
    bags              smallint check (bags >= 0),
    doors             smallint check (doors > 0),
    transmission      text check (transmission in ('automatic', 'manual')),
    air_conditioning  boolean not null default false,
    free_cancellation boolean not null default false,
    score             numeric(3, 1) check (score between 0 and 10),
    price_total       numeric(10, 2) not null check (price_total > 0),  -- total del alquiler
    currency          char(3) not null default 'USD',
    provider          text,
    source            text not null default 'kayak',
    scraped_at        timestamptz not null default now(),

    constraint cars_dates check (dropoff_date >= pickup_date),
    constraint cars_natural_key unique (kayak_id, pickup_date, dropoff_date)
);

create index cars_search_idx on cars.cars (pickup_airport, pickup_date, dropoff_date, price_total);

-- Reservas creadas por el SAGA. Una por orden: reintentar el paso devuelve la misma.
create table cars.reservations (
    id           uuid primary key default gen_random_uuid(),
    order_id     uuid not null,
    car_id       uuid not null references cars.cars (id),
    total_price  numeric(10, 2) not null check (total_price > 0),  -- congelado al reservar
    currency     char(3) not null,
    status       text not null default 'RESERVED' check (status in ('RESERVED', 'CANCELLED')),
    created_at   timestamptz not null default now(),
    cancelled_at timestamptz,

    constraint cars_reservations_order_key unique (order_id),
    constraint cars_reservations_cancelled_at check ((status = 'CANCELLED') = (cancelled_at is not null))
);
