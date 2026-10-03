-- Usuarios registrados. Las sesiones viven en Redis, no aquí.
create table identity.users (
    id            uuid primary key default gen_random_uuid(),
    email         text not null,
    password_hash text not null,
    full_name     text not null,
    created_at    timestamptz not null default now(),

    constraint users_email_format check (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    -- Solo se aceptan hashes Argon2id en formato PHC ($argon2id$v=19$m=...,t=...,p=...$sal$hash).
    constraint users_password_argon2id check (password_hash like '$argon2id$%')
);

create unique index users_email_key on identity.users (lower(email));
