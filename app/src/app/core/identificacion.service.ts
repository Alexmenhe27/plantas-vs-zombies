import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { ToastController } from '@ionic/angular';
import { ApiService, ErrorIdentificacion, estaEnLinea } from './api.service';
import { CatalogoService } from './catalogo.service';
import { CupoService } from './cupo.service';
import { FotosService } from './fotos.service';
import { vibrarExito } from './hapticos';
import { EventoIdentificacion, Parcial, ResultadoIdentificacion } from './modelos';
import { PendientesService } from './pendientes.service';
import { UbicacionService } from './ubicacion.service';

export interface FotoEnCurso {
  blob: Blob;
  vistaPrevia: string;
  tomadaEn: string;
}

/** subiendo -> analizando -> listo (o error / en_espera si no hay conexión). */
export type Fase = 'subiendo' | 'analizando' | 'listo' | 'error' | 'en_espera';

/** Errores para los que tiene sentido guardar la foto e identificarla después. */
const SE_PUEDE_ESPERAR = ['sin_conexion', 'servidor_inaccesible', 'subida_fallida', 'ia_no_disponible', 'servicio_saturado', 'base_de_datos', 'limite_diario'];

/**
 * El recorrido de una identificación: cámara -> foto comprimida -> subida -> resultado por partes -> ficha.
 * Vive en un servicio (no en la pantalla) para que siga aunque la persona cambie de pestaña.
 */
@Injectable({ providedIn: 'root' })
export class IdentificacionService {
  private readonly api = inject(ApiService);
  private readonly fotos = inject(FotosService);
  private readonly ubicacion = inject(UbicacionService);
  private readonly cupo = inject(CupoService);
  private readonly catalogo = inject(CatalogoService);
  private readonly pendientes = inject(PendientesService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastController);

  readonly foto = signal<FotoEnCurso | null>(null);
  readonly fase = signal<Fase>('subiendo');
  readonly parcial = signal<Parcial>({});
  readonly resultado = signal<ResultadoIdentificacion | null>(null);
  readonly error = signal<ErrorIdentificacion | null>(null);
  /** Abriendo la cámara o preparando la foto. */
  readonly ocupado = signal(false);
  readonly eligiendo = signal(false);
  readonly sePuedeEsperar = computed(() => SE_PUEDE_ESPERAR.includes(this.error()?.codigo ?? ''));
  private corrida = 0;

  /** Toma o elige la foto y empieza a identificar (botón central de la cámara y pantalla de inicio). */
  async empezar(origen: 'camara' | 'galeria'): Promise<void> {
    if (this.ocupado()) return;
    this.ocupado.set(true);
    // La ubicación se busca mientras la persona encuadra: cuando la foto termine de subir, ya estará lista.
    this.ubicacion.precargar();
    try {
      let original: Blob | null;
      try {
        original = await this.fotos.elegir(origen);
      } catch {
        await this.avisar(origen === 'camara' ? 'No se pudo abrir la cámara. Revisa el permiso en Ajustes.' : 'No se pudo abrir la galería.');
        return;
      }
      if (!original) return;
      let comprimida: Blob;
      try {
        comprimida = await this.fotos.comprimir(original);
      } catch {
        // Pasa sobre todo con fotos HEIC de iPhone abiertas en un navegador de computadora.
        await this.avisar('No pudimos leer esa imagen. Usa una foto JPG o PNG.');
        return;
      }
      this.iniciar(comprimida);
      await this.router.navigateByUrl('/identificar');
    } finally {
      this.ocupado.set(false);
    }
  }

  iniciar(blob: Blob, tomadaEn = new Date().toISOString()): void {
    this.limpiar();
    this.foto.set({ blob, vistaPrevia: URL.createObjectURL(blob), tomadaEn });
    void this.correr();
  }

  async reintentar(): Promise<void> {
    await this.correr();
  }

  private async correr(): Promise<void> {
    const id = ++this.corrida;
    const foto = this.foto();
    if (!foto) return;
    this.error.set(null);
    this.parcial.set({});
    this.resultado.set(null);
    if (!estaEnLinea()) {
      await this.guardarParaDespues();
      return;
    }
    this.fase.set('subiendo');
    const ubicacion = this.ubicacion.paraFoto(1500);
    let ruta: string | null = null;
    try {
      ruta = await this.fotos.subir(foto.blob).catch((e: unknown) => {
        if (!estaEnLinea()) throw new ErrorIdentificacion('sin_conexion', 'No pudimos enviar tu foto.');
        throw new ErrorIdentificacion('subida_fallida', e instanceof Error ? e.message : 'No pudimos guardar tu foto.');
      });
      const coords = await ubicacion;
      if (id !== this.corrida) return;
      this.fase.set('analizando');
      await this.api.identificar(
        { ruta_foto: ruta, latitud: coords?.latitud ?? null, longitud: coords?.longitud ?? null, observada_en: foto.tomadaEn },
        (e) => {
          if (id === this.corrida) this.alEvento(e);
        },
      );
      void this.fotos.subirMiniatura(ruta, foto.blob);
    } catch (e) {
      const err = e instanceof ErrorIdentificacion ? e : new ErrorIdentificacion('desconocido', 'Algo salió mal. Intenta de nuevo.');
      if (id !== this.corrida || this.resultado()) return;
      // La foto se subió pero no se guardó la observación: se borra para no dejar archivos sueltos.
      if (ruta) void this.fotos.borrar(ruta).catch(() => undefined);
      if (err.codigo === 'sin_conexion') {
        await this.guardarParaDespues();
        return;
      }
      if (err.codigo === 'sin_sesion') {
        await this.router.navigateByUrl('/bienvenida', { replaceUrl: true });
        return;
      }
      this.error.set(err);
      this.fase.set('error');
    }
  }

  private alEvento(e: EventoIdentificacion): void {
    if (e.tipo === 'parcial') {
      const { tipo: _, ...campos } = e;
      this.parcial.update((p) => ({ ...p, ...campos }));
    } else if (e.tipo === 'resultado') {
      this.resultado.set(e);
      this.fase.set('listo');
      this.cupo.descontar(e.restantes, e.limite);
      this.catalogo.invalidar();
      if (e.observacion.estado === 'identificada') void vibrarExito();
    } else if (e.tipo === 'ficha') {
      this.catalogo.actualizar(e.especie);
      const r = this.resultado();
      if (r && r.observacion.especie?.id === e.especie.id) {
        this.resultado.set({ ...r, ficha_pendiente: false, observacion: { ...r.observacion, especie: e.especie } });
      }
    }
  }

  /** Cuando la IA no estaba segura, la persona elige cuál de las parecidas es. */
  async elegir(nombreCientifico: string): Promise<void> {
    const r = this.resultado();
    if (!r || this.eligiendo()) return;
    this.eligiendo.set(true);
    try {
      const observacion = await this.api.elegir(r.observacion.id, nombreCientifico);
      this.resultado.set({ ...r, observacion: { ...r.observacion, ...observacion } });
      this.catalogo.invalidar();
      void vibrarExito();
    } catch (e) {
      await this.avisar(e instanceof Error ? e.message : 'No se pudo guardar tu elección.');
    } finally {
      this.eligiendo.set(false);
    }
  }

  /** Guarda la foto en el teléfono para identificarla sola cuando haya conexión (o se libere el cupo). */
  async guardarParaDespues(): Promise<void> {
    const foto = this.foto();
    if (!foto) return;
    const err = this.error();
    const coords = await this.ubicacion.paraFoto(300);
    await this.pendientes.agregar(foto.blob, foto.tomadaEn, coords,
      err?.codigo === 'limite_diario' ? err.disponibleEn : null,
      err?.codigo === 'limite_diario' ? 'Se identificará cuando se libere tu cupo del día.' : null);
    this.error.set(null);
    this.fase.set('en_espera');
  }

  descartar(): void {
    this.limpiar();
    void this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
  }

  limpiar(): void {
    this.corrida++;
    const f = this.foto();
    if (f) URL.revokeObjectURL(f.vistaPrevia);
    this.foto.set(null);
    this.parcial.set({});
    this.resultado.set(null);
    this.error.set(null);
    this.fase.set('subiendo');
  }

  private async avisar(mensaje: string): Promise<void> {
    const t = await this.toast.create({ message: mensaje, duration: 3500, color: 'dark' });
    await t.present();
  }
}
