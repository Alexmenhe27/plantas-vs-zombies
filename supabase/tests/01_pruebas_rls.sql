-- Pruebas de permisos (RLS). Cada bloque falla con una excepción si algo no se cumple.
\set ON_ERROR_STOP on
set client_min_messages = warning;

-- Usuarios de prueba: ana (user), beto (user), admin
insert into auth.users (id, email, raw_user_meta_data) values
 ('00000000-0000-0000-0000-00000000000a', 'ana@test.mx',   '{"nombre_usuario":"ana"}'),
 ('00000000-0000-0000-0000-00000000000b', 'beto@test.mx',  '{"nombre_usuario":"beto"}'),
 ('00000000-0000-0000-0000-0000000000ad', 'admin@test.mx', '{"nombre_usuario":"admin"}');
update public.perfiles set rol = 'admin' where id = '00000000-0000-0000-0000-0000000000ad';

do $$ begin
  assert (select count(*) from public.perfiles) = 3, 'el trigger debe crear 3 perfiles';
  assert (select rol from public.perfiles where nombre_usuario = 'ana') = 'usuario', 'rol por defecto = usuario';
  assert (select count(*) from public.especies) >= 80, 'catálogo sembrado';
end $$;

-- La API (service role) crea observaciones
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a/1.jpg',
       19.0414, -98.2063, id, 0.94, 'identificada', true from public.especies where nombre_cientifico = 'Ara militaris';
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a/2.jpg',
       19.0414, -98.2063, id, 0.90, 'identificada', false from public.especies where nombre_cientifico = 'Quiscalus mexicanus';
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-00000000000b', '00000000-0000-0000-0000-00000000000b/1.jpg',
       19.0414, -98.2063, id, 0.40, 'revisar', true from public.especies where nombre_cientifico = 'Romerolagus diazi';
insert into storage.objects (bucket_id, name) values
 ('fotos', '00000000-0000-0000-0000-00000000000a/1.jpg'),
 ('fotos', '00000000-0000-0000-0000-00000000000a/2.jpg'),
 ('fotos', '00000000-0000-0000-0000-00000000000b/1.jpg');

-- ===== Como beto (usuario normal) =====
set role authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-00000000000b';
do $$
declare n int;
begin
  assert (select count(*) from public.perfiles) = 1, 'beto solo ve su perfil';
  assert (select count(*) from public.observaciones) = 1, 'beto solo ve sus observaciones';
  assert (select count(*) from public.especies) >= 80, 'beto ve el catálogo';
  assert public.identificaciones_restantes() = 9, 'a beto le quedan 9';
  -- vista pública: ve la guacamaya de ana (pública, identificada) con ubicación redondeada; no la privada; no la de "revisar"
  assert (select count(*) from public.observaciones_publicas) = 1, 'vista pública: solo 1 observación publicable';
  assert (select latitud from public.observaciones_publicas) = 19.0, 'ubicación redondeada para especie protegida';
  -- fotos: la suya y la de la observación pública de ana; no la privada
  select count(*) into n from storage.objects;
  assert n = 2, format('beto debe ver 2 fotos, ve %s', n);
  -- puede subir a su carpeta, no a la de otro
  insert into storage.objects (bucket_id, name) values ('fotos', '00000000-0000-0000-0000-00000000000b/2.jpg');
  begin
    insert into storage.objects (bucket_id, name) values ('fotos', '00000000-0000-0000-0000-00000000000a/x.jpg');
    raise exception 'FALLO: subió a carpeta ajena';
  exception when insufficient_privilege then null;
  end;
  -- no puede crear observaciones directamente
  begin
    insert into public.observaciones (usuario_id, ruta_foto) values ('00000000-0000-0000-0000-00000000000b', 'x');
    raise exception 'FALLO: insertó observación sin la API';
  exception when insufficient_privilege then null;
  end;
  -- no puede hacerse admin
  begin
    update public.perfiles set rol = 'admin' where id = '00000000-0000-0000-0000-00000000000b';
    raise exception 'FALLO: cambió su rol';
  exception when raise_exception then
    if sqlerrm like 'FALLO%' then raise; end if;
  end;
  -- puede cambiar su username y si su observación es pública
  update public.perfiles set nombre_usuario = 'beto_nuevo' where id = '00000000-0000-0000-0000-00000000000b';
  update public.observaciones set es_publica = false where id = '10000000-0000-0000-0000-000000000003';
  -- no puede corregir la especie de su propia observación
  begin
    update public.observaciones set estado = 'identificada' where id = '10000000-0000-0000-0000-000000000003';
    raise exception 'FALLO: cambió el estado';
  exception when raise_exception then
    if sqlerrm like 'FALLO%' then raise; end if;
  end;
  -- no puede tocar observaciones ajenas (RLS: 0 filas)
  update public.observaciones set es_publica = false where id = '10000000-0000-0000-0000-000000000001';
  get diagnostics n = row_count;
  assert n = 0, 'no debe cambiar observaciones ajenas';
  delete from public.observaciones where id = '10000000-0000-0000-0000-000000000001';
  get diagnostics n = row_count;
  assert n = 0, 'no debe borrar observaciones ajenas';
  -- no puede crear especies
  begin
    insert into public.especies (nombre_comun, nombre_cientifico, reino, grupo) values ('x', 'x y', 'animal', 'ave');
    raise exception 'FALLO: creó especie';
  exception when insufficient_privilege then null;
  end;
end $$;

-- ===== Como admin =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000ad';
do $$
declare n int;
begin
  assert (select count(*) from public.perfiles) = 3, 'admin ve todos los perfiles';
  assert (select count(*) from public.observaciones) = 3, 'admin ve todas las observaciones';
  update public.observaciones set estado = 'corregida' where id = '10000000-0000-0000-0000-000000000003';
  get diagnostics n = row_count;
  assert n = 1, 'admin corrige';
  update public.perfiles set rol = 'admin' where id = '00000000-0000-0000-0000-00000000000b';
  update public.perfiles set rol = 'usuario' where id = '00000000-0000-0000-0000-00000000000b';
  insert into public.especies (nombre_comun, nombre_cientifico, reino, grupo) values ('Prueba', 'Prueba prueba', 'animal', 'ave');
  delete from public.especies where nombre_cientifico = 'Prueba prueba';
end $$;

-- Nombre de usuario único sin importar mayúsculas
reset role;
do $$ begin
  begin
    insert into auth.users (email, raw_user_meta_data) values ('ana2@test.mx', '{"nombre_usuario":"ANA"}');
    raise exception 'FALLO: permitió username duplicado';
  exception when unique_violation then null;
  end;
end $$;

-- ===== Sin sesión (anon) no ve nada =====
reset role;
set role anon;
set request.jwt.claim.sub = '';
do $$ begin
  begin
    perform count(*) from public.observaciones_publicas;
    raise exception 'FALLO: anon lee la vista pública';
  exception when insufficient_privilege then null;
  end;
  assert (select count(*) from public.especies) = 0, 'anon no ve el catálogo';
  assert public.nombre_usuario_disponible('ANA') = false, 'username ocupado (sin importar mayúsculas)';
  assert public.nombre_usuario_disponible('nuevo_nombre') = true, 'username libre';
end $$;
reset role;
select 'TODAS LAS PRUEBAS DE BASE DE DATOS PASARON' as resultado;
