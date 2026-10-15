import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { ToastController } from '@ionic/angular';
import { del, get, set } from 'idb-keyval';
import { ApiService, ErrorIdentificacion, estaEnLinea } from './api.service';
import { CatalogoService } from './catalogo.service';
import { CupoService } from './cupo.service';
import { FotosService } from './fotos.service';
import { SupabaseService } from './supabase.service';

/** Una foto guardada en el teléfono para identificarla cuando haya conexión (o cupo). */
interface Pendiente {
  id: string;
  usuarioId: string;
  blob: Blob;
  tomadaEn: string;
  latitud: number | null;
  longitud: number | null;
  /** No intentar antes de esta fecha (por ejemplo, cuando se libera el cupo del día). */
  esperarHasta: string | null;
  aviso: string | null;
  /** "limite": se espera a tener cupo (se reintenta antes si la persona ya tiene cupo, p. ej. al crear su cuenta). */
  motivo?: 'limite' | 'error' | null;
}

export interface PendienteVista {
  id: string;
  vistaPrevia: string;
  tomadaEn: string;
  aviso: string | null;
}

const CLAVE = 'fotos-pendientes';

/**
 * Cola de fotos sin identificar: en el campo muchas veces no hay señal. La foto se guarda en el teléfono (IndexedDB)
 * y se identifica sola en cuanto vuelve la conexión, sin que la persona tenga que hacer nada.
 */
@Injectable({ providedIn: 'root' })
export class PendientesService {
  private readonly api = inject(ApiService);
  private readonly fotos = inject(FotosService);
  private readonly sb = inject(SupabaseService);
  private readonly cupo = inject(CupoService);
  private readonly catalogo = inject(CatalogoService);
  private readonly toast = inject(ToastController);
  private readonly router = inject(Router);

  readonly lista = signal<PendienteVista[]>([]);
  readonly procesando = signal(false);
  private vistas = new Map<string, string>();

  constructor() {
    if (typeof window !== 'undefined') window.addEventListener('online', () => void this.procesar());
  }

  async agregar(blob: Blob, tomadaEn: string, coords: { latitud: number; longitud: number } | null, esperarHasta: string | null = null,
    aviso: string | null = null): Promise<void> {
    const usuarioId = this.sb.userId();
    if (!usuarioId) return;
    const todos = await this.leer();
    todos.push({ id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, usuarioId, blob, tomadaEn,
      latitud: coords?.latitud ?? null, longitud: coords?.longitud ?? null, esperarHasta, aviso, motivo: esperarHasta ? 'limite' : null });
    await this.escribir(todos);
  }

  async quitar(id: string): Promise<void> {
    await this.escribir((await this.leer()).filter((p) => p.id !== id));
  }

  /** Muestra las fotos en espera de la persona con sesión. */
  async cargar(): Promise<void> {
    this.publicar(await this.leer());
  }

  /** Identifica las fotos en espera (si hay conexión y sesión). Se llama al abrir la app, al volver la señal y en Inicio. */
  async procesar(): Promise<void> {
    if (this.procesando() || !estaEnLinea() || !this.sb.userId()) return;
    this.procesando.set(true);
    try {
      const hayCupo = (this.cupo.cupo()?.restantes ?? 0) > 0;
      for (const p of (await this.leer()).filter((x) => x.usuarioId === this.sb.userId())) {
        const esperaPorCupo = p.motivo === 'limite' && hayCupo;
        if (p.esperarHasta && new Date(p.esperarHasta).getTime() > Date.now() && !esperaPorCupo) continue;
        const seguir = await this.identificar(p);
        if (!seguir) break;
      }
    } finally {
      this.procesando.set(false);
      await this.cargar();
    }
  }

  /** Devuelve false si hay que dejar de intentar por ahora (sin conexión o sin cupo). */
  private async identificar(p: Pendiente): Promise<boolean> {
    let ruta: string | null = null;
    try {
      ruta = await this.fotos.subir(p.blob);
      const r = await this.api.identificar({ ruta_foto: ruta, latitud: p.latitud, longitud: p.longitud, observada_en: p.tomadaEn });
      void this.fotos.subirMiniatura(ruta, p.blob);
      await this.quitar(p.id);
      this.cupo.descontar(r.restantes, r.limite);
      this.catalogo.invalidar();
      const nombre = r.observacion.especie?.nombre_comun ?? r.observacion.ia_nombre_sugerido;
      const t = await this.toast.create({
        message: nombre ? `Tu foto en espera se identificó: ${nombre}` : 'Tu foto en espera ya tiene resultado.',
        duration: 6000, color: 'dark', position: 'top',
        buttons: [{ text: 'Ver', handler: () => void this.router.navigateByUrl(`/observacion/${r.observacion.id}`) }],
      });
      await t.present();
      return true;
    } catch (e) {
      if (ruta) void this.fotos.borrar(ruta).catch(() => undefined);
      const err = e instanceof ErrorIdentificacion ? e : null;
      if (!err || ['sin_conexion', 'servidor_inaccesible', 'subida_fallida'].includes(err.codigo)) return false;
      const todos = await this.leer();
      const item = todos.find((x) => x.id === p.id);
      if (item) {
        item.esperarHasta = err.codigo === 'limite_diario' ? err.disponibleEn ?? new Date(Date.now() + 3600_000).toISOString()
          : new Date(Date.now() + 10 * 60_000).toISOString();
        item.aviso = err.codigo === 'limite_diario' ? 'Se identificará cuando se libere tu cupo del día.' : err.message;
        item.motivo = err.codigo === 'limite_diario' ? 'limite' : 'error';
        await this.escribir(todos);
      }
      return err.codigo !== 'limite_diario' && err.codigo !== 'servicio_saturado';
    }
  }

  private async leer(): Promise<Pendiente[]> {
    try {
      return ((await get<Pendiente[]>(CLAVE)) ?? []).filter((p) => p && p.blob);
    } catch {
      return []; // sin IndexedDB (modo privado de algunos navegadores): no hay cola
    }
  }

  private async escribir(todos: Pendiente[]): Promise<void> {
    try {
      if (todos.length) await set(CLAVE, todos);
      else await del(CLAVE);
    } catch {
      // Sin IndexedDB no se puede guardar para después.
    }
    this.publicar(todos);
  }

  private publicar(todos: Pendiente[]): void {
    const mias = todos.filter((p) => p.usuarioId === this.sb.userId());
    const vigentes = new Set(mias.map((p) => p.id));
    for (const [id, url] of this.vistas) {
      if (!vigentes.has(id)) {
        URL.revokeObjectURL(url);
        this.vistas.delete(id);
      }
    }
    this.lista.set(mias.map((p) => {
      if (!this.vistas.has(p.id)) this.vistas.set(p.id, URL.createObjectURL(p.blob));
      return { id: p.id, vistaPrevia: this.vistas.get(p.id)!, tomadaEn: p.tomadaEn, aviso: p.aviso };
    }));
  }
}
