-- Plantas vs Zombies · Base de datos en español
-- Renombra tablas, columnas, vista, funciones, índices y restricciones al español.
-- NO borra datos ni objetos: todo se hace con "rename", y los pocos valores que cambian se convierten en el mismo paso.
--   profiles      -> perfiles
--   species       -> especies
--   observations  -> observaciones
--   public_observations -> observaciones_publicas
-- También agrega especies.imagen_fuente (página de la foto en Wikimedia Commons, para dar crédito).

begin;

-- ------------------------------------------------------------
-- 1. perfiles
-- ------------------------------------------------------------
alter table public.profiles rename to perfiles;
alter table public.perfiles rename column username   to nombre_usuario;
alter table public.perfiles rename column role       to rol;
alter table public.perfiles rename column created_at to creado_en;

alter table public.perfiles drop constraint if exists profiles_role_check;
alter table public.perfiles rename constraint profiles_username_check to perfiles_nombre_usuario_check;
alter table public.perfiles rename constraint profiles_id_fkey to perfiles_id_fkey;
alter index public.profiles_pkey rename to perfiles_pkey;
alter index public.profiles_username_unico rename to perfiles_nombre_usuario_unico;

-- ------------------------------------------------------------
-- 2. especies
-- ------------------------------------------------------------
alter table public.species rename to especies;
alter table public.especies rename column common_name     to nombre_comun;
alter table public.especies rename column scientific_name to nombre_cientifico;
alter table public.especies rename column kingdom         to reino;
alter table public.especies rename column is_protected    to protegida;
alter table public.especies rename column nom059_category to categoria_nom059;
alter table public.especies rename column is_introduced   to introducida;
alter table public.especies rename column family          to familia;
alter table public.especies rename column description     to descripcion;
alter table public.especies rename column image_url       to imagen_url;
alter table public.especies rename column created_at      to creado_en;
alter table public.especies add column if not exists imagen_fuente text;

alter table public.especies rename constraint species_kingdom_check to especies_reino_check;
alter table public.especies rename constraint species_nom059_category_check to especies_categoria_nom059_check;
alter index public.species_pkey rename to especies_pkey;
alter index public.species_scientific_name_key rename to especies_nombre_cientifico_key;
alter index public.species_kingdom_grupo_idx rename to especies_reino_grupo_idx;
alter sequence if exists public.species_id_seq rename to especies_id_seq;

-- ------------------------------------------------------------
-- 3. observaciones
-- ------------------------------------------------------------
alter table public.observations rename to observaciones;
alter table public.observaciones rename column user_id           to usuario_id;
alter table public.observaciones rename column photo_path        to ruta_foto;
alter table public.observaciones rename column latitude          to latitud;
alter table public.observaciones rename column longitude         to longitud;
alter table public.observaciones rename column observed_at       to observada_en;
alter table public.observaciones rename column species_id        to especie_id;
alter table public.observaciones rename column ai_confidence     to ia_confianza;
alter table public.observaciones rename column ai_explanation    to ia_explicacion;
alter table public.observaciones rename column ai_suggested_name to ia_nombre_sugerido;
alter table public.observaciones rename column ai_candidates     to ia_candidatos;
alter table public.observaciones rename column ai_issue          to ia_problema;
alter table public.observaciones rename column status            to estado;
alter table public.observaciones rename column is_public         to es_publica;
alter table public.observaciones rename column created_at        to creado_en;

alter table public.observaciones rename constraint observations_latitude_check      to observaciones_latitud_check;
alter table public.observaciones rename constraint observations_longitude_check     to observaciones_longitud_check;
alter table public.observaciones rename constraint observations_ai_confidence_check to observaciones_ia_confianza_check;
alter table public.observaciones rename constraint observations_ai_issue_check      to observaciones_ia_problema_check;
alter table public.observaciones rename constraint observations_status_check        to observaciones_estado_check;
alter table public.observaciones rename constraint observations_user_id_fkey        to observaciones_usuario_id_fkey;
alter table public.observaciones rename constraint observations_species_id_fkey     to observaciones_especie_id_fkey;
alter index public.observations_pkey             rename to observaciones_pkey;
alter index public.observations_user_created_idx rename to observaciones_usuario_creado_idx;
alter index public.observations_public_idx       rename to observaciones_publicas_idx;
alter index public.observations_status_idx       rename to observaciones_revisar_idx;

-- ------------------------------------------------------------
-- 4. Funciones y disparadores (se renombran y se reescribe su contenido)
-- ------------------------------------------------------------
alter function public.is_admin() rename to es_admin;
create or replace function public.es_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.perfiles p where p.id = auth.uid() and p.rol = 'admin');
$$;

alter function public.handle_new_user() rename to crear_perfil;
create or replace function public.crear_perfil()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.perfiles (id, nombre_usuario)
  values (new.id, nullif(coalesce(new.raw_user_meta_data ->> 'nombre_usuario', new.raw_user_meta_data ->> 'username'), ''));
  return new;
end;
$$;

alter function public.username_disponible(text) rename to nombre_usuario_disponible;
create or replace function public.nombre_usuario_disponible(nombre text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select not exists (select 1 from public.perfiles where lower(nombre_usuario) = lower(nombre));
$$;

alter function public.protect_profile_role() rename to proteger_rol_perfil;
create or replace function public.proteger_rol_perfil()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.rol is distinct from old.rol
     and auth.uid() is not null           -- las sesiones de servidor (SQL, service role) sí pueden
     and not public.es_admin() then
    raise exception 'Solo un administrador puede cambiar roles';
  end if;
  return new;
end;
$$;
alter trigger profiles_protect_role on public.perfiles rename to perfiles_proteger_rol;

alter function public.protect_observation_fields() rename to proteger_campos_observacion;
create or replace function public.proteger_campos_observacion()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if auth.uid() is not null and not public.es_admin()
     and (new.especie_id is distinct from old.especie_id
          or new.estado is distinct from old.estado) then
    raise exception 'Solo un administrador puede corregir la especie o el estado';
  end if;
  return new;
end;
$$;
alter trigger observations_protect_fields on public.observaciones rename to observaciones_proteger_campos;

create or replace function public.identificaciones_restantes()
returns integer
language sql
stable
security invoker
set search_path = ''
as $$
  select greatest(0, 10 - count(*))::integer
  from public.observaciones
  where usuario_id = auth.uid()
    and creado_en > now() - interval '24 hours';
$$;

-- ------------------------------------------------------------
-- 4b. Datos que cambian de valor (después de reescribir los disparadores)
-- ------------------------------------------------------------
update public.perfiles set rol = 'usuario' where rol = 'user';
alter table public.perfiles alter column rol set default 'usuario';
alter table public.perfiles add constraint perfiles_rol_check check (rol in ('usuario', 'admin'));

-- Las especies parecidas se guardaban como [{species_id, confianza}]; ahora [{especie_id, confianza}].
update public.observaciones
set ia_candidatos = (
  select coalesce(jsonb_agg(jsonb_build_object('especie_id', c -> 'species_id', 'confianza', c -> 'confianza')), '[]'::jsonb)
  from jsonb_array_elements(ia_candidatos) c
)
where jsonb_array_length(ia_candidatos) > 0 and ia_candidatos -> 0 ? 'species_id';

-- ------------------------------------------------------------
-- 5. Vista pública: se renombra junto con sus columnas. Su definición y la política de Storage
--    que la usa siguen funcionando porque Postgres las liga por id, no por nombre.
-- ------------------------------------------------------------
alter view public.public_observations rename to observaciones_publicas;
alter view public.observaciones_publicas rename column photo_path  to ruta_foto;
alter view public.observaciones_publicas rename column observed_at to observada_en;
alter view public.observaciones_publicas rename column species_id  to especie_id;
alter view public.observaciones_publicas rename column status      to estado;
alter view public.observaciones_publicas rename column created_at  to creado_en;
alter view public.observaciones_publicas rename column username    to nombre_usuario;
alter view public.observaciones_publicas rename column latitude    to latitud;
alter view public.observaciones_publicas rename column longitude   to longitud;

commit;
