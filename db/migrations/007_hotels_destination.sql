-- Código IATA del destino al que pertenece el hotel. Permite buscar paquetes
-- con la misma clave en vuelos, hoteles y autos ("MDE") sin que el gateway
-- conozca el formato de ciudad que usa Kayak.
alter table hotels.hotels add column destination char(3);

update hotels.hotels
set destination = case
    when city like 'Medellin,%' then 'MDE'
    when city like 'Cartagena,%' then 'CTG'
    when city like 'Santa Marta,%' then 'SMR'
end;

create index hotels_destination_idx on hotels.hotels (destination, checkin, checkout, price_per_night);
