-- Un esquema por microservicio. Ningún servicio lee ni escribe el esquema de otro,
-- y no hay llaves foráneas entre esquemas: los servicios se referencian por id.
create schema if not exists identity;  -- usuarios (gateway)
create schema if not exists flights;
create schema if not exists hotels;
create schema if not exists cars;
create schema if not exists orders;

-- Supabase expone algunos esquemas a sus roles públicos (anon, authenticated) a
-- través de su API REST/GraphQL. Estos esquemas solo se acceden desde los
-- microservicios con la cadena de conexión, así que se les quita todo acceso.
-- Los roles solo existen en Supabase; en un Postgres local se omite.
do $$
declare
    r text;
begin
    foreach r in array array['anon', 'authenticated'] loop
        if exists (select 1 from pg_roles where rolname = r) then
            execute format('revoke all on schema identity, flights, hotels, cars, orders from %I', r);
        end if;
    end loop;
end $$;
