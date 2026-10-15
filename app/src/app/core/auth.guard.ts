import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SupabaseService } from './supabase.service';

/** Solo deja pasar con sesión iniciada (con cuenta o como invitado). */
export const conSesion: CanActivateFn = async () => {
  const sb = inject(SupabaseService);
  const router = inject(Router);
  await sb.esperarInicio();
  return sb.session() ? true : router.parseUrl('/bienvenida');
};

/** Pantallas de acceso: si ya hay sesión, ir al inicio. Un invitado sí puede abrirlas (para crear su cuenta o entrar). */
export const sinSesion: CanActivateFn = async () => {
  const sb = inject(SupabaseService);
  const router = inject(Router);
  await sb.esperarInicio();
  return sb.session() && !sb.esInvitado() ? router.parseUrl('/app/inicio') : true;
};

/** Panel de revisión: solo administradores (la base de datos lo vuelve a comprobar). */
export const soloAdmin: CanActivateFn = async () => {
  const sb = inject(SupabaseService);
  const router = inject(Router);
  await sb.esperarInicio();
  if (!sb.session()) return router.parseUrl('/bienvenida');
  if (!sb.perfil()) await sb.cargarPerfil();
  return sb.esAdmin() ? true : router.parseUrl('/app/perfil');
};
