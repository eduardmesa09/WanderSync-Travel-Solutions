-- Órdenes, pagos y bitácora del SAGA (servicio de Órdenes/Facturación).

-- PENDING       el SAGA está ejecutando pasos
-- CONFIRMED     todos los pasos terminaron bien (happy path)
-- COMPENSATING  un paso falló y se están deshaciendo los anteriores
-- COMPENSATED   todas las compensaciones terminaron; no quedó nada reservado
-- FAILED        una compensación falló; requiere revisión manual
create table orders.orders (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null,  -- identity.users; sin FK porque es otro servicio
    flight_id        uuid,           -- flights.flights; sin FK por la misma razón
    hotel_id         uuid,
    car_id           uuid,
    passengers       smallint not null default 1 check (passengers > 0),
    total_amount     numeric(10, 2) not null check (total_amount >= 0),
    currency         char(3) not null default 'USD',
    status           text not null default 'PENDING'
        check (status in ('PENDING', 'CONFIRMED', 'COMPENSATING', 'COMPENSATED', 'FAILED')),
    failure_reason   text,
    -- Paso que se fuerza a fallar en la demo de compensaciones; null en uso normal.
    simulate_failure text check (simulate_failure in ('FLIGHT', 'HOTEL', 'CAR', 'PAYMENT')),
    -- Clave que envía el cliente para que un checkout repetido no cree dos órdenes.
    idempotency_key  text not null,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),

    constraint orders_has_items check (num_nonnulls(flight_id, hotel_id, car_id) > 0),
    constraint orders_idempotency_key unique (user_id, idempotency_key)
);

create index orders_user_idx on orders.orders (user_id, created_at desc);

create function orders.set_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end $$;

create trigger orders_set_updated_at
    before update on orders.orders
    for each row execute function orders.set_updated_at();

-- Bitácora del SAGA: solo se insertan filas, nunca se actualizan. Cada paso deja
-- una fila al empezar y otra al terminar, así se reconstruye la secuencia completa.
create table orders.saga_steps (
    id           bigint generated always as identity primary key,
    order_id     uuid not null references orders.orders (id) on delete cascade,
    step         text not null check (step in ('FLIGHT', 'HOTEL', 'CAR', 'PAYMENT')),
    action       text not null check (action in ('EXECUTE', 'COMPENSATE')),
    status       text not null check (status in ('STARTED', 'SUCCEEDED', 'FAILED')),
    reference_id uuid,  -- id de la reserva o del pago creado por el paso
    error        text,
    created_at   timestamptz not null default now()
);

create index saga_steps_order_idx on orders.saga_steps (order_id, id);

-- Pago simulado de la orden. Una por orden; la compensación lo marca REFUNDED.
create table orders.payments (
    id          uuid primary key default gen_random_uuid(),
    order_id    uuid not null references orders.orders (id),
    amount      numeric(10, 2) not null check (amount > 0),
    currency    char(3) not null,
    status      text not null check (status in ('CAPTURED', 'REFUNDED', 'FAILED')),
    created_at  timestamptz not null default now(),
    refunded_at timestamptz,

    constraint payments_order_key unique (order_id),
    constraint payments_refunded_at check ((status = 'REFUNDED') = (refunded_at is not null))
);
