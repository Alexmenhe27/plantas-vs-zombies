-- Plantas vs Zombies · Catálogo abierto
-- La app ya no se limita a Puebla: la IA identifica cualquier animal o planta y la especie se agrega
-- al catálogo la primera vez que alguien la fotografía. Así solo se guardan especies que de verdad se observan.
-- "verificada" distingue las 95 especies revisadas a mano (true) de las que agregó la IA (false), para revisarlas después.
-- No borra ni cambia datos existentes.

alter table public.especies add column if not exists verificada boolean not null default true;
alter table public.especies alter column verificada set default false;
comment on column public.especies.verificada is 'true = revisada por una persona; false = ficha creada por la IA, pendiente de revisión';
