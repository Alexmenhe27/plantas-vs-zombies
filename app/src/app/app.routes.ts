import { Routes } from '@angular/router';
import { conSesion, sinSesion, soloAdmin } from './core/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'app/inicio' },
  { path: 'bienvenida', canActivate: [sinSesion], loadComponent: () => import('./auth/bienvenida.page').then((m) => m.BienvenidaPage) },
  { path: 'entrar', canActivate: [sinSesion], loadComponent: () => import('./auth/login.page').then((m) => m.LoginPage) },
  { path: 'registro', canActivate: [sinSesion], loadComponent: () => import('./auth/registro.page').then((m) => m.RegistroPage) },
  { path: 'recuperar', loadComponent: () => import('./auth/recuperar.page').then((m) => m.RecuperarPage) },
  { path: 'nueva-contrasena', loadComponent: () => import('./auth/nueva-contrasena.page').then((m) => m.NuevaContrasenaPage) },
  {
    path: 'app',
    canActivate: [conSesion],
    loadComponent: () => import('./tabs/tabs.page').then((m) => m.TabsPage),
    children: [
      { path: 'inicio', loadComponent: () => import('./inicio/inicio.page').then((m) => m.InicioPage) },
      { path: 'explorar', loadComponent: () => import('./especies/catalogo.page').then((m) => m.CatalogoPage) },
      { path: 'coleccion', loadComponent: () => import('./coleccion/coleccion.page').then((m) => m.ColeccionPage) },
      { path: 'perfil', loadComponent: () => import('./perfil/perfil.page').then((m) => m.PerfilPage) },
      // Direcciones de la versión anterior
      { path: 'identificar', redirectTo: 'inicio' },
      { path: 'historial', redirectTo: 'coleccion' },
      { path: '', pathMatch: 'full', redirectTo: 'inicio' },
    ],
  },
  { path: 'identificar', canActivate: [conSesion], loadComponent: () => import('./identificar/identificar.page').then((m) => m.IdentificarPage) },
  { path: 'analizando', redirectTo: 'identificar' },
  { path: 'observacion/:id', canActivate: [conSesion], loadComponent: () => import('./observaciones/observacion.page').then((m) => m.ObservacionPage) },
  { path: 'especie/:id', canActivate: [conSesion], loadComponent: () => import('./especies/ficha.page').then((m) => m.FichaPage) },
  { path: 'revision', canActivate: [soloAdmin], loadComponent: () => import('./admin/revision.page').then((m) => m.RevisionPage) },
  { path: '**', redirectTo: 'app/inicio' },
];
