import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { SupabaseService } from './supabase.service';

/** Solo deja pasar con sesión iniciada. */
export const conSesion: CanActivateFn = async () => {
  const sb = inject(SupabaseService);
  const router = inject(Router);
  await sb.esperarInicio();
  return sb.session() ? true : router.parseUrl('/entrar');
};

/** Pantallas de acceso: si ya hay sesión, ir al inicio. */
export const sinSesion: CanActivateFn = async () => {
  const sb = inject(SupabaseService);
  const router = inject(Router);
  await sb.esperarInicio();
  return sb.session() ? router.parseUrl('/app/identificar') : true;
};
