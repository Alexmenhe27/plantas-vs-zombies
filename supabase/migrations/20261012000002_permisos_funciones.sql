-- Ajustes que pidió el asesor de seguridad de Supabase.
-- Por defecto Postgres deja ejecutar cualquier función a todos (rol public).

-- El trigger de registro no debe poder llamarse por la API.
revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- is_admin() la usan las políticas RLS de usuarios con sesión; sin sesión no hace falta.
revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- username_disponible() sí debe ser pública: el registro la consulta antes de tener sesión.
-- public_observations se queda como vista con permisos del dueño A PROPÓSITO: deja ver
-- observaciones públicas de otros usuarios sin exponer la tabla, y redondea la ubicación de
-- especies protegidas. Solo usuarios con sesión pueden consultarla.
