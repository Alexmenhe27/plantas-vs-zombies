-- Rendimiento, seguridad y privacidad (14 de octubre de 2026)
--
-- 1. Límite diario a prueba de trucos: se cuenta en "uso_ia", un registro que la app no puede borrar
--    (antes contaba las observaciones, y al borrar una se recuperaba el cupo). La API reserva el cupo
--    ANTES de llamar a la IA, con un candado por persona, así que peticiones simultáneas no lo rebasan.
--    Invitados (inicio de sesión anónimo): límite propio y por red, para que no se abuse creando cuentas.
--    Tope global diario para proteger el saldo de la IA. Todos los números viven en "ajustes".
-- 2. Privacidad: las observaciones nuevas son privadas por defecto (las que ya existían también pasan a privadas).
--    En lo público la ubicación siempre es aproximada (~10 km) y en especies protegidas no se muestra.
--    La vista observaciones_publicas (marcada como ERROR por el asesor de seguridad de Supabase) se cambia
--    por una función que solo devuelve lo que se puede publicar.
-- 3. Una sola llamada para guardar el resultado (antes eran 2 o 3 viajes a la base de datos).
-- 4. La persona puede elegir entre las especies parecidas (estado "elegida") y pedir revisión.
-- 5. Colección personal, búsqueda sin acentos, índices y políticas RLS más rápidas.
-- No borra datos de las personas. Solo elimina el esquema temporal tmp_imagenes (sus datos están en seed_imagenes.sql).

begin;

drop schema if exists tmp_imagenes cascade;

-- ============================================================
-- 1. Ajustes (fuente única de los límites)
-- ============================================================
create table if not exists public.ajustes (
  clave       text primary key,
  valor       integer not null check (valor >= 0),
  descripcion text
);
alter table public.ajustes enable row level security;
drop policy if exists "Con sesión se leen los ajustes" on public.ajustes;
create policy "Con sesión se leen los ajustes" on public.ajustes for select to authenticated using (true);
drop policy if exists "Solo admin cambia los ajustes" on public.ajustes;
create policy "Solo admin cambia los ajustes" on public.ajustes for update to authenticated
  using ((select public.es_admin())) with check ((select public.es_admin()));

insert into public.ajustes (clave, valor, descripcion) values
  ('limite_diario', 10, 'Identificaciones por persona en 24 horas'),
  ('limite_diario_invitado', 3, 'Identificaciones por invitado (sin cuenta) en 24 horas'),
  ('limite_invitados_por_red', 15, 'Identificaciones de invitados desde una misma red (IP) en 24 horas'),
  ('limite_global_diario', 500, 'Tope total de identificaciones por día entre todas las personas (protege el saldo de la IA)')
on conflict (clave) do nothing;

-- ============================================================
-- 2. Perfiles: preferencia de publicación (privado por defecto)
-- ============================================================
alter table public.perfiles add column if not exists publicar_por_defecto boolean not null default false;

-- ============================================================
-- 3. Especies: validación con GBIF y búsqueda sin acentos
-- ============================================================
alter table public.especies add column if not exists gbif_id bigint;
alter table public.especies add column if not exists busqueda text;
comment on column public.especies.gbif_id is 'Clave del nombre aceptado en GBIF (la API valida cada especie nueva ahí)';

create or replace function public.normalizar_texto(t text)
returns text
language sql
immutable
parallel safe
set search_path = ''
as $$
  select lower(translate(coalesce(t, ''), 'ÁÉÍÓÚÜÑáéíóúüñÀÈÌÒÙàèìòù', 'AEIOUUNaeiouunAEIOUaeiou'));
$$;

create or replace function public.especies_busqueda()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.busqueda := public.normalizar_texto(new.nombre_comun || ' ' || new.nombre_cientifico);
  return new;
end;
$$;

drop trigger if exists especies_busqueda on public.especies;
create trigger especies_busqueda
  before insert or update of nombre_comun, nombre_cientifico on public.especies
  for each row execute function public.especies_busqueda();

update public.especies set busqueda = public.normalizar_texto(nombre_comun || ' ' || nombre_cientifico);

-- Índice de trigramas para buscar por parte del nombre (si el servidor tiene pg_trgm, como Supabase).
do $$
begin
  if exists (select 1 from pg_available_extensions where name = 'pg_trgm') then
    create schema if not exists extensions;
    create extension if not exists pg_trgm with schema extensions;
    execute 'create index if not exists especies_busqueda_trgm on public.especies using gin (busqueda extensions.gin_trgm_ops)';
  end if;
end;
$$;

-- ============================================================
-- 4. Observaciones: nuevo estado, privadas por defecto e índices
-- ============================================================
alter table public.observaciones drop constraint if exists observaciones_estado_check;
alter table public.observaciones add constraint observaciones_estado_check
  check (estado in ('identificada', 'revisar', 'elegida', 'corregida', 'no_identificada'));
comment on column public.observaciones.estado is
  'identificada (IA segura), revisar (IA con dudas), elegida (la persona eligió entre las parecidas), corregida (por un admin), no_identificada';

alter table public.observaciones alter column es_publica set default false;
update public.observaciones set es_publica = false where es_publica;

create index if not exists observaciones_especie_idx on public.observaciones (especie_id);
create index if not exists observaciones_ruta_foto_idx on public.observaciones (ruta_foto);
drop index if exists public.observaciones_revisar_idx;
create index observaciones_revisar_idx on public.observaciones (creado_en desc) where estado in ('revisar', 'elegida');

-- La especie y el estado solo los cambia un admin, salvo dentro de funciones autorizadas (marcar_para_revision).
create or replace function public.proteger_campos_observacion()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if auth.uid() is not null and not public.es_admin()
     and coalesce(current_setting('app.cambio_autorizado', true), '') <> 'si'
     and (new.especie_id is distinct from old.especie_id
          or new.estado is distinct from old.estado) then
    raise exception 'Solo un administrador puede corregir la especie o el estado';
  end if;
  return new;
end;
$$;

-- ============================================================
-- 5. Políticas RLS: (select auth.uid()) se evalúa una vez por consulta y no por cada fila
-- ============================================================
drop policy if exists "Cada quien ve su perfil; admin ve todos" on public.perfiles;
create policy "Cada quien ve su perfil; admin ve todos" on public.perfiles for select to authenticated
  using (id = (select auth.uid()) or (select public.es_admin()));

drop policy if exists "Cada quien edita su perfil; admin edita todos" on public.perfiles;
create policy "Cada quien edita su perfil; admin edita todos" on public.perfiles for update to authenticated
  using (id = (select auth.uid()) or (select public.es_admin()))
  with check (id = (select auth.uid()) or (select public.es_admin()));

drop policy if exists "Cada quien ve las suyas; admin ve todas" on public.observaciones;
create policy "Cada quien ve las suyas; admin ve todas" on public.observaciones for select to authenticated
  using (usuario_id = (select auth.uid()) or (select public.es_admin()));

drop policy if exists "Cada quien cambia las suyas; admin cambia todas" on public.observaciones;
create policy "Cada quien cambia las suyas; admin cambia todas" on public.observaciones for update to authenticated
  using (usuario_id = (select auth.uid()) or (select public.es_admin()))
  with check (usuario_id = (select auth.uid()) or (select public.es_admin()));

drop policy if exists "Cada quien borra las suyas; admin borra todas" on public.observaciones;
create policy "Cada quien borra las suyas; admin borra todas" on public.observaciones for delete to authenticated
  using (usuario_id = (select auth.uid()) or (select public.es_admin()));

drop policy if exists "Solo admin crea especies" on public.especies;
create policy "Solo admin crea especies" on public.especies for insert to authenticated
  with check ((select public.es_admin()));
drop policy if exists "Solo admin edita especies" on public.especies;
create policy "Solo admin edita especies" on public.especies for update to authenticated
  using ((select public.es_admin())) with check ((select public.es_admin()));
drop policy if exists "Solo admin borra especies" on public.especies;
create policy "Solo admin borra especies" on public.especies for delete to authenticated
  using ((select public.es_admin()));

-- ============================================================
-- 6. Lo público: función segura en lugar de la vista
-- ============================================================
drop policy if exists "Ver mis fotos, las de observaciones públicas; admin ve todas" on storage.objects;
drop policy if exists "Ver mis fotos y las públicas; admin ve todas" on storage.objects;
drop view if exists public.observaciones_publicas;

-- ¿La foto (o su miniatura .mini.jpg) pertenece a una observación pública?
create or replace function public.es_foto_publica(p_ruta text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.observaciones o
    where (o.ruta_foto = p_ruta or o.ruta_foto = regexp_replace(p_ruta, '\.mini\.jpg$', '.jpg'))
      and o.es_publica and o.estado in ('identificada', 'elegida', 'corregida')
  );
$$;
revoke execute on function public.es_foto_publica(text) from public, anon;
grant execute on function public.es_foto_publica(text) to authenticated;

create policy "Ver mis fotos y las públicas; admin ve todas" on storage.objects for select to authenticated
  using (
    bucket_id = 'fotos' and (
      (storage.foldername(name))[1] = (select auth.uid())::text
      or (select public.es_admin())
      or public.es_foto_publica(name)
    )
  );

drop policy if exists "Subir fotos a mi carpeta" on storage.objects;
create policy "Subir fotos a mi carpeta" on storage.objects for insert to authenticated
  with check (bucket_id = 'fotos' and (storage.foldername(name))[1] = (select auth.uid())::text);

drop policy if exists "Borrar mis fotos; admin borra todas" on storage.objects;
create policy "Borrar mis fotos; admin borra todas" on storage.objects for delete to authenticated
  using (bucket_id = 'fotos' and ((storage.foldername(name))[1] = (select auth.uid())::text or (select public.es_admin())));

-- Avistamientos públicos: ubicación aproximada (~10 km) y sin ubicación si la especie está protegida.
create or replace function public.avistamientos_publicos(p_especie_id bigint default null, p_limite integer default 50)
returns table (
  id uuid, ruta_foto text, observada_en timestamptz, especie_id bigint, estado text,
  nombre_usuario text, latitud double precision, longitud double precision,
  nombre_comun text, nombre_cientifico text, grupo text, reino text, protegida boolean
)
language sql
stable
security definer
set search_path = ''
as $$
  select o.id, o.ruta_foto, o.observada_en, o.especie_id, o.estado, p.nombre_usuario,
         case when e.protegida or o.latitud is null then null else round(o.latitud::numeric, 1)::double precision end,
         case when e.protegida or o.longitud is null then null else round(o.longitud::numeric, 1)::double precision end,
         e.nombre_comun, e.nombre_cientifico, e.grupo, e.reino, e.protegida
  from public.observaciones o
  join public.perfiles p on p.id = o.usuario_id
  join public.especies e on e.id = o.especie_id
  where o.es_publica and o.estado in ('identificada', 'elegida', 'corregida')
    and (p_especie_id is null or o.especie_id = p_especie_id)
  order by o.observada_en desc
  limit least(greatest(coalesce(p_limite, 50), 1), 300);
$$;
revoke execute on function public.avistamientos_publicos(bigint, integer) from public, anon;
grant execute on function public.avistamientos_publicos(bigint, integer) to authenticated;

-- ============================================================
-- 7. Registro de uso de la IA (el límite diario se cuenta aquí)
-- ============================================================
create table if not exists public.uso_ia (
  id             bigint generated always as identity primary key,
  usuario_id     uuid references auth.users (id) on delete set null,
  red            text,                       -- huella anónima de la IP (solo invitados); se borra a los 3 días
  es_invitado    boolean not null default false,
  estado         text not null default 'reservada' check (estado in ('reservada', 'usada')),
  observacion_id uuid references public.observaciones (id) on delete set null,
  creado_en      timestamptz not null default now()
);
create index if not exists uso_ia_usuario_idx on public.uso_ia (usuario_id, creado_en desc);
create index if not exists uso_ia_red_idx on public.uso_ia (red, creado_en desc) where es_invitado;
create index if not exists uso_ia_creado_idx on public.uso_ia (creado_en);
create index if not exists uso_ia_observacion_idx on public.uso_ia (observacion_id);
alter table public.uso_ia enable row level security;
-- Sin políticas: nadie lo lee ni lo borra desde la app. Solo la API (service role) y las funciones de abajo.
revoke all on public.uso_ia from anon, authenticated;

-- Las identificaciones de las últimas 24 horas siguen contando después de la migración.
insert into public.uso_ia (usuario_id, estado, observacion_id, creado_en)
select o.usuario_id, 'usada', o.id, o.creado_en
from public.observaciones o
where o.creado_en > now() - interval '24 hours'
  and not exists (select 1 from public.uso_ia u where u.observacion_id = o.id);

-- Reserva un lugar ANTES de llamar a la IA. Con un candado por persona: dos peticiones al mismo tiempo no rebasan el límite.
create or replace function public.reservar_identificacion(p_usuario uuid, p_red text default null)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_invitado boolean;
  v_limite   integer;
  v_global   integer;
  v_red      integer;
  v_usadas   integer;
  v_primera  timestamptz;
  v_id       bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended('uso_ia:' || p_usuario::text, 0));
  select coalesce(u.is_anonymous, false) into v_invitado from auth.users u where u.id = p_usuario;
  if not found then
    return jsonb_build_object('ok', false, 'motivo', 'sin_usuario');
  end if;

  select valor into v_global from public.ajustes where clave = 'limite_global_diario';
  if v_global is not null and (select count(*) from public.uso_ia where creado_en > now() - interval '24 hours') >= v_global then
    return jsonb_build_object('ok', false, 'motivo', 'limite_global');
  end if;

  select valor into v_limite from public.ajustes
  where clave = case when v_invitado then 'limite_diario_invitado' else 'limite_diario' end;
  v_limite := coalesce(v_limite, 10);

  if v_invitado and p_red is not null then
    perform pg_advisory_xact_lock(hashtextextended('uso_ia_red:' || p_red, 0));
    select valor into v_red from public.ajustes where clave = 'limite_invitados_por_red';
    select count(*), min(creado_en) into v_usadas, v_primera from public.uso_ia
    where red = p_red and es_invitado and creado_en > now() - interval '24 hours';
    if v_red is not null and v_usadas >= v_red then
      return jsonb_build_object('ok', false, 'motivo', 'limite_red', 'limite', v_limite, 'invitado', true,
                                'disponible_en', v_primera + interval '24 hours');
    end if;
  end if;

  select count(*), min(creado_en) into v_usadas, v_primera from public.uso_ia
  where usuario_id = p_usuario and creado_en > now() - interval '24 hours';
  if v_usadas >= v_limite then
    return jsonb_build_object('ok', false, 'motivo', 'limite_diario', 'limite', v_limite, 'invitado', v_invitado,
                              'disponible_en', v_primera + interval '24 hours');
  end if;

  insert into public.uso_ia (usuario_id, red, es_invitado)
  values (p_usuario, case when v_invitado then p_red end, v_invitado)
  returning id into v_id;

  -- Limpieza: lo de hace más de 3 días ya no cuenta para ningún límite.
  delete from public.uso_ia where creado_en < now() - interval '3 days';

  return jsonb_build_object('ok', true, 'reserva', v_id, 'limite', v_limite, 'invitado', v_invitado,
                            'restantes', greatest(0, v_limite - v_usadas - 1));
end;
$$;

-- Si la IA falla (no es culpa de la persona) se devuelve el lugar.
create or replace function public.liberar_identificacion(p_reserva bigint)
returns void
language sql
security definer
set search_path = ''
as $$
  delete from public.uso_ia where id = p_reserva and estado = 'reservada';
$$;

-- Guarda el resultado en un solo viaje: busca la especie (o la crea), decide el estado,
-- guarda la observación, enlaza las especies parecidas y marca el uso de la IA.
create or replace function public.guardar_identificacion(p_reserva bigint, p_datos jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_especie    public.especies;
  v_creada     boolean := false;
  v_confianza  numeric := coalesce((p_datos ->> 'confianza')::numeric, 0);
  v_nueva      jsonb := p_datos -> 'nueva_especie';
  v_estado     text;
  v_publica    boolean;
  v_candidatos jsonb;
  v_obs        public.observaciones;
begin
  if p_datos ->> 'problema' = 'ninguno' then
    select e.* into v_especie
    from jsonb_array_elements_text(coalesce(p_datos -> 'nombres', '[]'::jsonb)) with ordinality as n(nombre, orden)
    join public.especies e on e.nombre_cientifico = n.nombre
    order by n.orden
    limit 1;

    if v_especie.id is null and jsonb_typeof(v_nueva) = 'object'
       and v_confianza >= coalesce((p_datos ->> 'confianza_para_catalogo')::numeric, 0.5) then
      insert into public.especies (nombre_cientifico, nombre_comun, reino, grupo, familia, gbif_id, verificada)
      values (v_nueva ->> 'nombre_cientifico', v_nueva ->> 'nombre_comun', v_nueva ->> 'reino', v_nueva ->> 'grupo',
              v_nueva ->> 'familia', (v_nueva ->> 'gbif_id')::bigint, false)
      on conflict (nombre_cientifico) do nothing
      returning * into v_especie;
      if v_especie.id is null then
        select * into v_especie from public.especies where nombre_cientifico = v_nueva ->> 'nombre_cientifico';
      else
        v_creada := true;
      end if;
    end if;
  end if;

  v_estado := case
    when p_datos ->> 'problema' <> 'ninguno' then 'no_identificada'
    when v_especie.id is null or v_confianza < coalesce((p_datos ->> 'confianza_minima')::numeric, 0.7) then 'revisar'
    else 'identificada'
  end;

  select coalesce(p.publicar_por_defecto, false) into v_publica
  from public.perfiles p where p.id = (p_datos ->> 'usuario_id')::uuid;

  select coalesce(jsonb_agg(c.valor || jsonb_build_object('especie_id', e.id) order by c.orden), '[]'::jsonb)
  into v_candidatos
  from jsonb_array_elements(coalesce(p_datos -> 'candidatos', '[]'::jsonb)) with ordinality as c(valor, orden)
  left join public.especies e on e.nombre_cientifico = c.valor ->> 'nombre_cientifico';

  insert into public.observaciones (
    usuario_id, ruta_foto, latitud, longitud, observada_en, especie_id, ia_confianza, ia_explicacion,
    ia_nombre_sugerido, ia_candidatos, ia_problema, estado, es_publica
  ) values (
    (p_datos ->> 'usuario_id')::uuid, p_datos ->> 'ruta_foto',
    (p_datos ->> 'latitud')::double precision, (p_datos ->> 'longitud')::double precision,
    coalesce((p_datos ->> 'observada_en')::timestamptz, now()),
    v_especie.id, round(v_confianza, 3), p_datos ->> 'explicacion', p_datos ->> 'nombre_sugerido', v_candidatos,
    nullif(p_datos ->> 'problema', 'ninguno'), v_estado,
    coalesce(v_publica, false) and v_estado in ('identificada', 'revisar')
  )
  returning * into v_obs;

  update public.uso_ia set estado = 'usada', observacion_id = v_obs.id where id = p_reserva;

  return jsonb_build_object(
    'observacion', to_jsonb(v_obs) || jsonb_build_object(
      'especie', case when v_especie.id is null then null else to_jsonb(v_especie) - 'busqueda' end),
    'especie_creada', v_creada,
    'candidatos_especies', (
      select coalesce(jsonb_agg(to_jsonb(e) - 'busqueda'), '[]'::jsonb)
      from public.especies e
      where e.id in (select (x ->> 'especie_id')::bigint from jsonb_array_elements(v_candidatos) x)
    )
  );
end;
$$;

revoke execute on function public.reservar_identificacion(uuid, text) from public, anon, authenticated;
revoke execute on function public.liberar_identificacion(bigint) from public, anon, authenticated;
revoke execute on function public.guardar_identificacion(bigint, jsonb) from public, anon, authenticated;
grant execute on function public.reservar_identificacion(uuid, text) to service_role;
grant execute on function public.liberar_identificacion(bigint) to service_role;
grant execute on function public.guardar_identificacion(bigint, jsonb) to service_role;

-- Cupo de la persona con sesión (lo muestra la app).
create or replace function public.mi_cupo()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_uid      uuid := auth.uid();
  v_invitado boolean;
  v_limite   integer;
  v_usadas   integer;
  v_primera  timestamptz;
begin
  if v_uid is null then
    return null;
  end if;
  select coalesce(u.is_anonymous, false) into v_invitado from auth.users u where u.id = v_uid;
  select valor into v_limite from public.ajustes
  where clave = case when coalesce(v_invitado, false) then 'limite_diario_invitado' else 'limite_diario' end;
  v_limite := coalesce(v_limite, 10);
  select count(*), min(creado_en) into v_usadas, v_primera from public.uso_ia
  where usuario_id = v_uid and creado_en > now() - interval '24 hours';
  return jsonb_build_object(
    'limite', v_limite, 'usadas', v_usadas, 'restantes', greatest(0, v_limite - v_usadas),
    'invitado', coalesce(v_invitado, false),
    'disponible_en', case when v_usadas >= v_limite then v_primera + interval '24 hours' end
  );
end;
$$;
revoke execute on function public.mi_cupo() from public, anon;
grant execute on function public.mi_cupo() to authenticated;

-- Se conserva para versiones anteriores de la app.
create or replace function public.identificaciones_restantes()
returns integer
language sql
stable
security invoker
set search_path = ''
as $$
  select coalesce((public.mi_cupo() ->> 'restantes')::integer, 0);
$$;
revoke execute on function public.identificaciones_restantes() from public, anon;
grant execute on function public.identificaciones_restantes() to authenticated;

-- ============================================================
-- 8. Colección y revisión
-- ============================================================
-- Especies que la persona ha encontrado (con RLS: solo las suyas).
create or replace function public.mi_coleccion()
returns table (especie jsonb, veces integer, primera_vez timestamptz, ultima_vez timestamptz, ruta_foto text)
language sql
stable
security invoker
set search_path = ''
as $$
  select to_jsonb(e) - 'busqueda', count(*)::integer, min(o.observada_en), max(o.observada_en),
         (array_agg(o.ruta_foto order by o.observada_en desc))[1]
  from public.observaciones o
  join public.especies e on e.id = o.especie_id
  where o.usuario_id = (select auth.uid()) and o.estado in ('identificada', 'elegida', 'corregida')
  group by e.id
  order by max(o.observada_en) desc;
$$;
revoke execute on function public.mi_coleccion() from public, anon;
grant execute on function public.mi_coleccion() to authenticated;

-- "No es correcto": la persona manda su observación a revisión (y puede elegir entre las parecidas).
create or replace function public.marcar_para_revision(p_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform set_config('app.cambio_autorizado', 'si', true);
  update public.observaciones set estado = 'revisar'
  where id = p_id and usuario_id = auth.uid() and estado in ('identificada', 'elegida');
  if not found then
    raise exception 'Esta observación no se puede mandar a revisión';
  end if;
  perform set_config('app.cambio_autorizado', '', true);
end;
$$;
revoke execute on function public.marcar_para_revision(uuid) from public, anon;
grant execute on function public.marcar_para_revision(uuid) to authenticated;

commit;
