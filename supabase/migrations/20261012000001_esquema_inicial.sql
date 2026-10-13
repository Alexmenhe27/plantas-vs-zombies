-- Esquema inicial
-- Tres tablas: profiles, species, observations. RLS en todas.
-- Bucket privado "fotos" con una carpeta por usuario.

-- ============================================================
-- 1. Perfiles (1 a 1 con auth.users)
-- ============================================================
create table public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  username   text check (char_length(username) between 3 and 30),
  role       text not null default 'user' check (role in ('user', 'admin')),
  created_at timestamptz not null default now()
);

-- Nombre de usuario único sin distinguir mayúsculas.
create unique index profiles_username_unico on public.profiles (lower(username));

-- ¿El usuario actual es administrador? (security definer para no chocar con RLS)
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role = 'admin'
  );
$$;

-- Al registrarse, crear el perfil con rol "user".
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, username)
  values (new.id, nullif(new.raw_user_meta_data ->> 'username', ''));
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ¿Está libre un nombre de usuario? (se usa en el registro, antes de tener sesión)
create or replace function public.username_disponible(nombre text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select not exists (select 1 from public.profiles where lower(username) = lower(nombre));
$$;

grant execute on function public.username_disponible(text) to anon, authenticated;

-- Solo un admin puede cambiar roles (el primer admin se asigna a mano con SQL).
create or replace function public.protect_profile_role()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.role is distinct from old.role
     and auth.uid() is not null           -- las sesiones de servidor (SQL, service role) sí pueden
     and not public.is_admin() then
    raise exception 'Solo un administrador puede cambiar roles';
  end if;
  return new;
end;
$$;

create trigger profiles_protect_role
  before update on public.profiles
  for each row execute function public.protect_profile_role();

alter table public.profiles enable row level security;

create policy "Cada quien ve su perfil; admin ve todos"
  on public.profiles for select to authenticated
  using (id = auth.uid() or public.is_admin());

create policy "Cada quien edita su perfil; admin edita todos"
  on public.profiles for update to authenticated
  using (id = auth.uid() or public.is_admin())
  with check (id = auth.uid() or public.is_admin());

-- ============================================================
-- 2. Catálogo de especies de Puebla
-- ============================================================
create table public.species (
  id              bigint generated always as identity primary key,
  common_name     text not null,
  scientific_name text not null unique,
  kingdom         text not null check (kingdom in ('animal', 'planta')),
  grupo           text not null,           -- ave, mamífero, reptil, anfibio, insecto, árbol, cactácea, ...
  is_protected    boolean not null default false,  -- listada en la NOM-059-SEMARNAT
  nom059_category text check (nom059_category in ('P', 'A', 'Pr', 'E')), -- en peligro, amenazada, protección especial, extinta
  is_introduced   boolean not null default false,  -- especie exótica / introducida
  family          text,
  description     text,
  habitat         text,
  alimentacion    text,
  tamano          text,
  image_url       text,
  created_at      timestamptz not null default now()
);

create index species_kingdom_grupo_idx on public.species (kingdom, grupo);

alter table public.species enable row level security;

create policy "Cualquier usuario con sesión ve el catálogo"
  on public.species for select to authenticated
  using (true);

create policy "Solo admin crea especies"
  on public.species for insert to authenticated
  with check (public.is_admin());

create policy "Solo admin edita especies"
  on public.species for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

create policy "Solo admin borra especies"
  on public.species for delete to authenticated
  using (public.is_admin());

-- ============================================================
-- 3. Observaciones (cada foto identificada)
-- ============================================================
create table public.observations (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.profiles (id) on delete cascade,
  photo_path     text not null,            -- ruta dentro del bucket "fotos": <user_id>/<archivo>.jpg
  latitude       double precision check (latitude between -90 and 90),
  longitude      double precision check (longitude between -180 and 180),
  observed_at    timestamptz not null default now(),
  species_id     bigint references public.species (id) on delete set null,
  ai_confidence  real check (ai_confidence between 0 and 1),
  ai_explanation text,
  ai_suggested_name text,                  -- lo que Claude cree que es, aunque no esté en el catálogo
  ai_candidates  jsonb not null default '[]', -- especies parecidas [{species_id, nombre, confianza}]
  ai_issue       text check (ai_issue in ('borrosa', 'sin_organismo')), -- por qué la foto no sirvió
  status         text not null default 'identificada'
                 check (status in ('identificada', 'revisar', 'corregida', 'no_identificada')),
  is_public      boolean not null default true,
  created_at     timestamptz not null default now()
);

create index observations_user_created_idx on public.observations (user_id, created_at desc);
create index observations_public_idx on public.observations (created_at desc) where is_public;
create index observations_status_idx on public.observations (status) where status = 'revisar';

alter table public.observations enable row level security;

-- Las observaciones se crean solo desde la API en Python (service role), no hay política de insert.

create policy "Cada quien ve las suyas; admin ve todas"
  on public.observations for select to authenticated
  using (user_id = auth.uid() or public.is_admin());

create policy "Cada quien cambia las suyas; admin cambia todas"
  on public.observations for update to authenticated
  using (user_id = auth.uid() or public.is_admin())
  with check (user_id = auth.uid() or public.is_admin());

create policy "Cada quien borra las suyas; admin borra todas"
  on public.observations for delete to authenticated
  using (user_id = auth.uid() or public.is_admin());

-- Un usuario normal solo puede cambiar "is_public"; especie y estado los corrige un admin.
revoke update on public.observations from authenticated;
grant update (is_public, species_id, status) on public.observations to authenticated;

create or replace function public.protect_observation_fields()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if auth.uid() is not null and not public.is_admin()
     and (new.species_id is distinct from old.species_id
          or new.status is distinct from old.status) then
    raise exception 'Solo un administrador puede corregir la especie o el estado';
  end if;
  return new;
end;
$$;

create trigger observations_protect_fields
  before update on public.observations
  for each row execute function public.protect_observation_fields();

-- ============================================================
-- 4. Vista pública: observaciones públicas de todos, con ubicación
--    redondeada (~10 km) cuando la especie está protegida.
-- ============================================================
create view public.public_observations
with (security_barrier = true)
as
select
  o.id,
  o.photo_path,
  o.observed_at,
  o.species_id,
  o.status,
  o.created_at,
  p.username,
  case when s.is_protected then round(o.latitude::numeric, 1)::double precision  else o.latitude  end as latitude,
  case when s.is_protected then round(o.longitude::numeric, 1)::double precision else o.longitude end as longitude
from public.observations o
join public.profiles p on p.id = o.user_id
left join public.species s on s.id = o.species_id
where o.is_public and o.status in ('identificada', 'corregida');

revoke all on public.public_observations from anon, public;
grant select on public.public_observations to authenticated;

-- ============================================================
-- 5. Límite diario: cuántas identificaciones le quedan al usuario
-- ============================================================
create or replace function public.identificaciones_restantes()
returns integer
language sql
stable
security invoker
set search_path = ''
as $$
  select greatest(0, 10 - count(*))::integer
  from public.observations
  where user_id = auth.uid()
    and created_at > now() - interval '24 hours';
$$;

grant execute on function public.identificaciones_restantes() to authenticated;

-- ============================================================
-- 6. Storage: bucket privado "fotos", carpeta por usuario, máx. 5 MB
-- ============================================================
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('fotos', 'fotos', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

create policy "Subir fotos a mi carpeta"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "Ver mis fotos, las de observaciones públicas; admin ve todas"
  on storage.objects for select to authenticated
  using (
    bucket_id = 'fotos' and (
      (storage.foldername(name))[1] = auth.uid()::text
      or public.is_admin()
      or exists (
        select 1 from public.public_observations po where po.photo_path = storage.objects.name
      )
    )
  );

create policy "Borrar mis fotos; admin borra todas"
  on storage.objects for delete to authenticated
  using (bucket_id = 'fotos' and ((storage.foldername(name))[1] = auth.uid()::text or public.is_admin()));
