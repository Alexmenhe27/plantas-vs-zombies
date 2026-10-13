import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner } from '@ionic/angular';
import { environment } from '../../environments/environment';
import { ApiService, CodigoError, ErrorIdentificacion, estaEnLinea } from '../core/api.service';
import { CatalogoService } from '../core/catalogo.service';
import { tiempoHasta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { IdentificacionService } from '../core/identificacion.service';
import { UbicacionService } from '../core/ubicacion.service';

type Paso = 'foto' | 'ubicacion' | 'ia' | 'ficha';

@Component({
  selector: 'app-analizando',
  imports: [IonContent, IonIcon, IonSpinner, RouterLink],
  templateUrl: './analizando.page.html',
  styleUrl: './analizando.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalizandoPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly fotos = inject(FotosService);
  private readonly ubicacion = inject(UbicacionService);
  private readonly identificacion = inject(IdentificacionService);
  private readonly catalogo = inject(CatalogoService);
  private readonly router = inject(Router);

  readonly limite = environment.limiteDiario;
  readonly foto = this.identificacion.pendiente;
  readonly paso = signal<Paso>('foto');
  readonly sinUbicacion = signal(false);
  readonly error = signal<ErrorIdentificacion | null>(null);
  readonly codigo = computed<CodigoError | null>(() => this.error()?.codigo ?? null);
  readonly esperar = computed(() => {
    const d = this.error()?.disponibleEn;
    return d ? tiempoHasta(d) : null;
  });
  private cancelado = false;

  ngOnInit(): void {
    if (!this.foto()) {
      void this.router.navigateByUrl('/app/identificar', { replaceUrl: true });
      return;
    }
    void this.analizar();
  }

  ngOnDestroy(): void {
    this.cancelado = true;
  }

  hecho(p: Paso): boolean {
    const orden: Paso[] = ['foto', 'ubicacion', 'ia', 'ficha'];
    return orden.indexOf(p) < orden.indexOf(this.paso());
  }

  async analizar(): Promise<void> {
    const pendiente = this.foto();
    if (!pendiente) return;
    this.error.set(null);
    let ruta: string | null = null;
    try {
      this.paso.set('foto');
      // La ubicación se pide mientras la foto se sube, para no sumar los dos tiempos.
      const ubicacion = this.ubicacion.actual();
      ruta = await this.fotos.subir(pendiente.blob).catch((e: unknown) => {
        // Antes cualquier fallo de la subida se mostraba como "sin internet"; ahora se distingue la causa real.
        if (!estaEnLinea()) throw new ErrorIdentificacion('sin_conexion', 'No pudimos enviar tu foto.');
        throw new ErrorIdentificacion('subida_fallida', e instanceof Error ? e.message : 'No pudimos guardar tu foto.');
      });
      this.paso.set('ubicacion');
      const coords = await ubicacion;
      this.sinUbicacion.set(!coords);
      this.paso.set('ia');
      const r = await this.api.identificar({
        ruta_foto: ruta,
        latitud: coords?.latitud ?? null,
        longitud: coords?.longitud ?? null,
        observada_en: pendiente.tomadaEn,
      });
      this.catalogo.invalidar();
      if (this.cancelado) return;
      this.paso.set('ficha');
      this.identificacion.limpiar();
      await this.router.navigate(['/observacion', r.observacion.id], { replaceUrl: true, queryParams: { nueva: 1 } });
    } catch (e) {
      // Si la foto ya se subió pero no se guardó la observación, se borra para no dejar archivos sueltos.
      if (ruta) void this.fotos.borrar(ruta).catch(() => undefined);
      const err = e instanceof ErrorIdentificacion ? e : new ErrorIdentificacion('desconocido', 'Algo salió mal. Intenta de nuevo.');
      if (err.codigo === 'sin_sesion') {
        await this.router.navigateByUrl('/entrar', { replaceUrl: true });
        return;
      }
      this.error.set(err);
    }
  }

  identificacionLimpia(): void {
    this.identificacion.limpiar();
  }

  descartar(): void {
    this.identificacion.limpiar();
    void this.router.navigateByUrl('/app/identificar', { replaceUrl: true });
  }
}
