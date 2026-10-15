-- Los administradores (perfiles.rol = 'admin') no tienen límite de identificaciones.
-- mi_cupo() les devuelve sin_limite = true (la app muestra "Sin límite").
-- La API deja pasar a los administradores cuando reservar_identificacion() dice que ya no hay lugar.
-- Solo redefine una función; no toca datos.

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
  v_admin    boolean;
begin
  if v_uid is null then
    return null;
  end if;
  select exists (select 1 from public.perfiles p where p.id = v_uid and p.rol = 'admin') into v_admin;
  if v_admin then
    return jsonb_build_object('limite', 9999, 'usadas', 0, 'restantes', 9999, 'invitado', false, 'disponible_en', null, 'sin_limite', true);
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
