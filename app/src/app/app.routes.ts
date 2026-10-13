import { Routes } from '@angular/router';
import { conSesion, sinSesion } from './core/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'app/identificar' },
  { path: 'entrar', canActivate: [sinSesion], loadComponent: () => import('./auth/login.page').then((m) => m.LoginPage) },
  { path: 'registro', canActivate: [sinSesion], loadComponent: () => import('./auth/registro.page').then((m) => m.RegistroPage) },
  { path: 'recuperar', loadComponent: () => import('./auth/recuperar.page').then((m) => m.RecuperarPage) },
  { path: 'nueva-contrasena', loadComponent: () => import('./auth/nueva-contrasena.page').then((m) => m.NuevaContrasenaPage) },
  {
    path: 'app',
    canActivate: [conSesion],
    loadComponent: () => import('./tabs/tabs.page').then((m) => m.TabsPage),
    children: [
      { path: 'identificar', loadComponent: () => import('./identificar/inicio.page').then((m) => m.InicioPage) },
      { path: 'explorar', loadComponent: () => import('./especies/catalogo.page').then((m) => m.CatalogoPage) },
      { path: 'historial', loadComponent: () => import('./observaciones/historial.page').then((m) => m.HistorialPage) },
      { path: 'perfil', loadComponent: () => import('./perfil/perfil.page').then((m) => m.PerfilPage) },
      { path: '', pathMatch: 'full', redirectTo: 'identificar' },
    ],
  },
  { path: 'analizando', canActivate: [conSesion], loadComponent: () => import('./identificar/analizando.page').then((m) => m.AnalizandoPage) },
  { path: 'observacion/:id', canActivate: [conSesion], loadComponent: () => import('./observaciones/observacion.page').then((m) => m.ObservacionPage) },
  { path: 'especie/:id', canActivate: [conSesion], loadComponent: () => import('./especies/ficha.page').then((m) => m.FichaPage) },
  { path: '**', redirectTo: 'app/identificar' },
];
