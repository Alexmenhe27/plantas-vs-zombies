-- Pruebas de permisos (RLS), límite diario, privacidad y funciones. Cada bloque falla con una excepción si algo no se cumple.
\set ON_ERROR_STOP on
set client_min_messages = warning;

-- Usuarios de prueba: ana (usuario), beto (usuario), admin e inv (invitado: inicio de sesión anónimo)
insert into auth.users (id, email, raw_user_meta_data, is_anonymous) values
 ('00000000-0000-0000-0000-00000000000a', 'ana@test.mx',   '{"nombre_usuario":"ana"}', false),
 ('00000000-0000-0000-0000-00000000000b', 'beto@test.mx',  '{"nombre_usuario":"beto"}', false),
 ('00000000-0000-0000-0000-0000000000ad', 'admin@test.mx', '{"nombre_usuario":"admin"}', false),
 ('00000000-0000-0000-0000-0000000000c1', null,            '{}', true);
update public.perfiles set rol = 'admin' where id = '00000000-0000-0000-0000-0000000000ad';

do $$ begin
  assert (select count(*) from public.perfiles) = 4, 'el trigger debe crear 4 perfiles (también al invitado)';
  assert (select rol from public.perfiles where nombre_usuario = 'ana') = 'usuario', 'rol por defecto = usuario';
  assert (select count(*) from public.especies) >= 80, 'catálogo sembrado';
  assert (select busqueda from public.especies where nombre_cientifico = 'Ara militaris') like '%guacamaya verde ara militaris%', 'columna de búsqueda';
  assert public.normalizar_texto('Búho Cornudo ÑANDÚ') = 'buho cornudo nandu', 'búsqueda sin acentos';
  assert (select valor from public.ajustes where clave = 'limite_diario') = 10, 'ajustes sembrados';
end $$;

-- La API (service role) crea observaciones. Por defecto son privadas.
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado)
select '10000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a/9.jpg',
       19.0414, -98.2063, id, 0.9, 'identificada' from public.especies where nombre_cientifico = 'Canis latrans';
do $$ begin
  assert (select es_publica from public.observaciones where id = '10000000-0000-0000-0000-000000000009') = false, 'privada por defecto';
end $$;
delete from public.observaciones where id = '10000000-0000-0000-0000-000000000009';

insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a/1.jpg',
       19.0414, -98.2063, id, 0.94, 'identificada', true from public.especies where nombre_cientifico = 'Ara militaris';
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a/2.jpg',
       19.0414, -98.2063, id, 0.90, 'identificada', false from public.especies where nombre_cientifico = 'Quiscalus mexicanus';
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-00000000000b', '00000000-0000-0000-0000-00000000000b/1.jpg',
       19.0414, -98.2063, id, 0.40, 'revisar', true from public.especies where nombre_cientifico = 'Romerolagus diazi';
insert into public.observaciones (id, usuario_id, ruta_foto, latitud, longitud, especie_id, ia_confianza, estado, es_publica)
select '10000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-00000000000a/4.jpg',
       19.0414, -98.2063, id, 0.92, 'identificada', true from public.especies where nombre_cientifico = 'Canis latrans';
insert into storage.objects (bucket_id, name) values
 ('fotos', '00000000-0000-0000-0000-00000000000a/1.jpg'),
 ('fotos', '00000000-0000-0000-0000-00000000000a/1.mini.jpg'),
 ('fotos', '00000000-0000-0000-0000-00000000000a/2.jpg'),
 ('fotos', '00000000-0000-0000-0000-00000000000a/4.jpg'),
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
  assert (public.mi_cupo() ->> 'restantes')::int = 10, 'el cupo se cuenta en uso_ia, no en las observaciones';
  assert public.identificaciones_restantes() = 10, 'función anterior sigue funcionando';
  -- avistamientos públicos: la guacamaya (protegida, sin ubicación) y el coyote (ubicación aproximada); no lo privado ni lo de "revisar"
  assert (select count(*) from public.avistamientos_publicos()) = 2, 'solo 2 avistamientos publicables';
  assert (select latitud from public.avistamientos_publicos() where nombre_cientifico = 'Ara militaris') is null, 'especie protegida: sin ubicación';
  assert (select latitud from public.avistamientos_publicos() where nombre_cientifico = 'Canis latrans') = 19.0, 'ubicación aproximada (~10 km)';
  assert (select count(*) from public.avistamientos_publicos((select id from public.especies where nombre_cientifico = 'Canis latrans'))) = 1, 'filtro por especie';
  -- fotos: la suya, las de observaciones públicas de ana (y la miniatura); no la privada
  select count(*) into n from storage.objects;
  assert n = 4, format('beto debe ver 4 fotos, ve %s', n);
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
  -- no puede leer ni borrar el registro de uso, ni reservar sin la API
  begin
    perform count(*) from public.uso_ia;
    raise exception 'FALLO: leyó uso_ia';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.reservar_identificacion('00000000-0000-0000-0000-00000000000b'::uuid, null);
    raise exception 'FALLO: reservó sin la API';
  exception when insufficient_privilege then null;
  end;
  -- no puede hacerse admin
  begin
    update public.perfiles set rol = 'admin' where id = '00000000-0000-0000-0000-00000000000b';
    raise exception 'FALLO: cambió su rol';
  exception when raise_exception then
    if sqlerrm like 'FALLO%' then raise; end if;
  end;
  -- puede cambiar su nombre, su preferencia de publicación y si su observación es pública
  update public.perfiles set nombre_usuario = 'beto_nuevo', publicar_por_defecto = true where id = '00000000-0000-0000-0000-00000000000b';
  update public.observaciones set es_publica = false where id = '10000000-0000-0000-0000-000000000003';
  -- no puede corregir el estado de su propia observación
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
  -- no puede mandar a revisión una observación ajena
  begin
    perform public.marcar_para_revision('10000000-0000-0000-0000-000000000001');
    raise exception 'FALLO: mandó a revisión una observación ajena';
  exception when raise_exception then
    if sqlerrm like 'FALLO%' then raise; end if;
  end;
  -- no puede crear especies ni cambiar ajustes
  begin
    insert into public.especies (nombre_comun, nombre_cientifico, reino, grupo) values ('x', 'x y', 'animal', 'ave');
    raise exception 'FALLO: creó especie';
  exception when insufficient_privilege then null;
  end;
  update public.ajustes set valor = 999 where clave = 'limite_diario';
  get diagnostics n = row_count;
  assert n = 0, 'no debe cambiar los ajustes';
end $$;

-- ===== Como ana: colección y "no es correcto" =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-00000000000a';
do $$ begin
  assert (select count(*) from public.mi_coleccion()) = 3, 'ana tiene 3 especies en su colección';
  perform public.marcar_para_revision('10000000-0000-0000-0000-000000000002');
  assert (select estado from public.observaciones where id = '10000000-0000-0000-0000-000000000002') = 'revisar', 'quedó en revisión';
  assert (select count(*) from public.mi_coleccion()) = 2, 'lo que está en revisión no cuenta en la colección';
  -- sigue sin poder cambiar el estado por su cuenta
  begin
    update public.observaciones set estado = 'identificada' where id = '10000000-0000-0000-0000-000000000002';
    raise exception 'FALLO: ana cambió el estado';
  exception when raise_exception then
    if sqlerrm like 'FALLO%' then raise; end if;
  end;
end $$;

-- ===== Límite diario (lo usa la API con la clave de servicio) =====
reset role;
set role service_role;
do $$
declare r jsonb; reservas bigint[] := '{}';
begin
  for i in 1..10 loop
    r := public.reservar_identificacion('00000000-0000-0000-0000-00000000000b', null);
    assert (r ->> 'ok')::boolean, format('reserva %s debe pasar: %s', i, r);
    reservas := reservas || (r ->> 'reserva')::bigint;
  end loop;
  assert (r ->> 'restantes')::int = 0, 'después de 10 no quedan';
  r := public.reservar_identificacion('00000000-0000-0000-0000-00000000000b', null);
  assert not (r ->> 'ok')::boolean and r ->> 'motivo' = 'limite_diario' and r ->> 'disponible_en' is not null, format('la 11 se rechaza: %s', r);
  -- si la IA falla se devuelve el lugar
  perform public.liberar_identificacion(reservas[10]);
  r := public.reservar_identificacion('00000000-0000-0000-0000-00000000000b', null);
  assert (r ->> 'ok')::boolean, 'tras liberar se puede reservar de nuevo';
end $$;

-- Guardar: especie existente, especie nueva, confianza baja y foto borrosa. El admin publica por defecto.
do $$
declare r jsonb; res bigint;
begin
  res := (public.reservar_identificacion('00000000-0000-0000-0000-00000000000a', null) ->> 'reserva')::bigint;
  r := public.guardar_identificacion(res, jsonb_build_object(
    'usuario_id', '00000000-0000-0000-0000-00000000000a', 'ruta_foto', '00000000-0000-0000-0000-00000000000a/10.jpg',
    'latitud', 19.04, 'longitud', -98.2, 'problema', 'ninguno', 'confianza', 0.95, 'explicacion', 'Frente roja.',
    'nombre_sugerido', 'Guacamaya verde (Ara militaris)', 'nombres', jsonb_build_array('Ara militaris'),
    'candidatos', jsonb_build_array(jsonb_build_object('nombre_cientifico', 'Ara militaris', 'nombre_comun', 'Guacamaya verde', 'confianza', 0.95),
                                    jsonb_build_object('nombre_cientifico', 'Ara macao', 'nombre_comun', 'Guacamaya roja', 'confianza', 0.03)),
    'confianza_minima', 0.7, 'confianza_para_catalogo', 0.5));
  assert r -> 'observacion' ->> 'estado' = 'identificada', format('identificada: %s', r);
  assert (r -> 'observacion' ->> 'es_publica')::boolean = false, 'ana no publica por defecto';
  assert r -> 'observacion' -> 'especie' ->> 'nombre_comun' = 'Guacamaya verde', 'trae la especie';
  assert r -> 'observacion' -> 'especie' ->> 'busqueda' is null, 'no expone la columna de búsqueda';
  assert (r -> 'observacion' -> 'ia_candidatos' -> 0 ->> 'especie_id') is not null, 'candidato enlazado al catálogo';
  assert (r -> 'observacion' -> 'ia_candidatos' -> 1 -> 'especie_id') = 'null'::jsonb, 'candidato fuera del catálogo';
  assert jsonb_array_length(r -> 'candidatos_especies') = 1, 'devuelve las especies parecidas del catálogo';
  assert (select estado from public.uso_ia where id = res) = 'usada', 'el uso queda registrado';

  -- especie nueva (con el nombre aceptado por GBIF) y publicación por defecto de beto
  res := (public.reservar_identificacion('00000000-0000-0000-0000-0000000000ad', null) ->> 'reserva')::bigint;
  update public.perfiles set publicar_por_defecto = true where id = '00000000-0000-0000-0000-0000000000ad';
  r := public.guardar_identificacion(res, jsonb_build_object(
    'usuario_id', '00000000-0000-0000-0000-0000000000ad', 'ruta_foto', '00000000-0000-0000-0000-0000000000ad/1.jpg',
    'problema', 'ninguno', 'confianza', 0.9, 'nombres', jsonb_build_array('Turdus rufopaliatus', 'Turdus rufopalliatus'),
    'nueva_especie', jsonb_build_object('nombre_cientifico', 'Turdus rufopalliatus', 'nombre_comun', 'Mirlo dorso rufo',
                                        'reino', 'animal', 'grupo', 'ave', 'familia', 'Turdidae', 'gbif_id', 2490718),
    'confianza_minima', 0.7, 'confianza_para_catalogo', 0.5));
  assert (r ->> 'especie_creada')::boolean, 'especie creada';
  assert r -> 'observacion' ->> 'estado' = 'identificada', 'nueva especie identificada';
  assert (r -> 'observacion' ->> 'es_publica')::boolean, 'publica por defecto si así lo eligió';
  assert (select verificada from public.especies where nombre_cientifico = 'Turdus rufopalliatus') = false, 'queda sin verificar';
  assert (select gbif_id from public.especies where nombre_cientifico = 'Turdus rufopalliatus') = 2490718, 'guarda la clave de GBIF';

  -- confianza baja: no llena el catálogo y queda en revisión
  r := public.guardar_identificacion(null, jsonb_build_object(
    'usuario_id', '00000000-0000-0000-0000-00000000000a', 'ruta_foto', '00000000-0000-0000-0000-00000000000a/11.jpg',
    'problema', 'ninguno', 'confianza', 0.3, 'nombres', jsonb_build_array('Pajarus dudosus'),
    'nueva_especie', jsonb_build_object('nombre_cientifico', 'Pajarus dudosus', 'nombre_comun', 'Dudoso', 'reino', 'animal', 'grupo', 'ave'),
    'confianza_minima', 0.7, 'confianza_para_catalogo', 0.5));
  assert r -> 'observacion' ->> 'estado' = 'revisar', 'confianza baja -> revisar';
  assert not exists (select 1 from public.especies where nombre_cientifico = 'Pajarus dudosus'), 'no se creó la especie dudosa';

  -- foto borrosa
  r := public.guardar_identificacion(null, jsonb_build_object(
    'usuario_id', '00000000-0000-0000-0000-00000000000a', 'ruta_foto', '00000000-0000-0000-0000-00000000000a/12.jpg',
    'problema', 'borrosa', 'confianza', 0, 'explicacion', 'Acércate más.'));
  assert r -> 'observacion' ->> 'estado' = 'no_identificada' and r -> 'observacion' ->> 'ia_problema' = 'borrosa', 'borrosa';
end $$;

-- Borrar observaciones NO devuelve el cupo (antes sí: era la forma de saltarse el límite)
do $$
declare antes int; despues int;
begin
  select count(*) into antes from public.uso_ia where usuario_id = '00000000-0000-0000-0000-00000000000a' and creado_en > now() - interval '24 hours';
  delete from public.observaciones where usuario_id = '00000000-0000-0000-0000-00000000000a' and ruta_foto like '%/1_.jpg';
  select count(*) into despues from public.uso_ia where usuario_id = '00000000-0000-0000-0000-00000000000a' and creado_en > now() - interval '24 hours';
  assert antes = despues and antes >= 1, format('borrar no devuelve el cupo (%s -> %s)', antes, despues);
end $$;

-- Invitados: límite propio (3) y por red
do $$
declare r jsonb;
begin
  for i in 1..3 loop
    r := public.reservar_identificacion('00000000-0000-0000-0000-0000000000c1', 'red-1');
    assert (r ->> 'ok')::boolean and (r ->> 'invitado')::boolean, format('invitado %s: %s', i, r);
  end loop;
  r := public.reservar_identificacion('00000000-0000-0000-0000-0000000000c1', 'red-1');
  assert r ->> 'motivo' = 'limite_diario' and (r ->> 'limite')::int = 3, format('invitado: límite de 3: %s', r);
end $$;
reset role;
-- Muchos invitados desde la misma red
insert into auth.users (id, is_anonymous) select gen_random_uuid(), true from generate_series(1, 6);
do $$
declare r jsonb; u uuid; aceptadas int := 3;  -- ya hubo 3 desde red-1
begin
  for u in select id from auth.users where is_anonymous and id <> '00000000-0000-0000-0000-0000000000c1' loop
    for i in 1..3 loop
      r := public.reservar_identificacion(u, 'red-1');
      if (r ->> 'ok')::boolean then aceptadas := aceptadas + 1; end if;
    end loop;
  end loop;
  assert aceptadas = 15, format('máximo 15 de invitados por red, hubo %s', aceptadas);
  assert r ->> 'motivo' = 'limite_red', format('motivo: %s', r);
end $$;

-- Tope global
reset role;
update public.ajustes set valor = 1 where clave = 'limite_global_diario';
set role service_role;
do $$ begin
  assert public.reservar_identificacion('00000000-0000-0000-0000-00000000000a', null) ->> 'motivo' = 'limite_global', 'tope global';
end $$;
reset role;
update public.ajustes set valor = 500 where clave = 'limite_global_diario';

-- ===== Como el invitado: su cupo =====
set role authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000c1';
do $$ begin
  assert (public.mi_cupo() ->> 'invitado')::boolean, 'mi_cupo sabe que es invitado';
  assert (public.mi_cupo() ->> 'restantes')::int = 0 and public.mi_cupo() ->> 'disponible_en' is not null, 'sin cupo y con hora';
end $$;

-- ===== Como admin =====
set request.jwt.claim.sub = '00000000-0000-0000-0000-0000000000ad';
do $$
declare n int;
begin
  assert (select count(*) from public.perfiles) >= 4, 'admin ve todos los perfiles';
  assert (select count(*) from public.observaciones where estado in ('revisar', 'elegida')) >= 2, 'admin ve lo que está en revisión';
  update public.observaciones set estado = 'corregida' where id = '10000000-0000-0000-0000-000000000003';
  get diagnostics n = row_count;
  assert n = 1, 'admin corrige';
  update public.perfiles set rol = 'admin' where id = '00000000-0000-0000-0000-00000000000b';
  update public.perfiles set rol = 'usuario' where id = '00000000-0000-0000-0000-00000000000b';
  insert into public.especies (nombre_comun, nombre_cientifico, reino, grupo) values ('Prueba', 'Prueba prueba', 'animal', 'ave');
  update public.especies set verificada = true where nombre_cientifico = 'Turdus rufopalliatus';
  delete from public.especies where nombre_cientifico = 'Prueba prueba';
  update public.ajustes set valor = 10 where clave = 'limite_diario';
  get diagnostics n = row_count;
  assert n = 1, 'admin cambia ajustes';
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
    perform count(*) from public.avistamientos_publicos();
    raise exception 'FALLO: anon lee los avistamientos';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.mi_cupo();
    raise exception 'FALLO: anon llama a mi_cupo';
  exception when insufficient_privilege then null;
  end;
  assert (select count(*) from public.especies) = 0, 'anon no ve el catálogo';
  assert public.nombre_usuario_disponible('ANA') = false, 'username ocupado (sin importar mayúsculas)';
  assert public.nombre_usuario_disponible('nuevo_nombre') = true, 'username libre';
end $$;
reset role;
select 'TODAS LAS PRUEBAS DE BASE DE DATOS PASARON' as resultado;
