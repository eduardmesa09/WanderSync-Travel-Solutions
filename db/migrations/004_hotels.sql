-- Catálogo de hoteles, alimentado por la ingesta (Kayak). Kayak cotiza por
-- fechas de estadía, así que cada fila es un hotel para un rango de fechas.
create table hotels.hotels (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    city            text not null,
    checkin         date not null,
    checkout        date not null,
    price_per_night numeric(10, 2) not null check (price_per_night > 0),
    currency        char(3) not null default 'USD',
    stars           smallint check (stars between 1 and 5),
    rating          numeric(3, 1) check (rating between 0 and 10),
    review_count    integer check (review_count >= 0),
    distance_miles  numeric(6, 1) check (distance_miles >= 0),
    free_breakfast  boolean not null default false,
    source          text not null default 'kayak',
    scraped_at      timestamptz not null default now(),

    constraint hotels_dates check (checkout > checkin),
    constraint hotels_natural_key unique (name, city, checkin, checkout)
);

create index hotels_search_idx on hotels.hotels (city, checkin, checkout, price_per_night);

-- Reservas creadas por el SAGA. Una por orden: reintentar el paso devuelve la misma.
create table hotels.reservations (
    id           uuid primary key default gen_random_uuid(),
    order_id     uuid not null,
    hotel_id     uuid not null references hotels.hotels (id),
    rooms        smallint not null default 1 check (rooms > 0),
    nights       smallint not null check (nights > 0),
    total_price  numeric(10, 2) not null check (total_price > 0),  -- congelado al reservar
    currency     char(3) not null,
    status       text not null default 'RESERVED' check (status in ('RESERVED', 'CANCELLED')),
    created_at   timestamptz not null default now(),
    cancelled_at timestamptz,

    constraint hotels_reservations_order_key unique (order_id),
    constraint hotels_reservations_cancelled_at check ((status = 'CANCELLED') = (cancelled_at is not null))
);
