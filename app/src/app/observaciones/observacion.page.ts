import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AlertController, IonContent, IonIcon, IonToggle, NavController, ToastController, ViewWillEnter } from '@ionic/angular';
import { ApiService } from '../core/api.service';
import { CatalogoService } from '../core/catalogo.service';
import { fechaCorta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { vibrarExito } from '../core/hapticos';
import { Especie, Observacion } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { SupabaseService } from '../core/supabase.service';
import { compartirObservacion } from '../shared/compartir';
import { FotoAnalisisComponent } from '../shared/foto-analisis.component';
import { ResultadoComponent } from '../shared/resultado/resultado.component';

/** Una observación guardada: el mismo resultado, más publicar, compartir, "no es correcto" y borrar. */
@Component({
  selector: 'app-observacion',
  imports: [FotoAnalisisComponent, ResultadoComponent, IonContent, IonIcon, IonToggle, RouterLink],
  templateUrl: './observacion.page.html',
  styleUrl: './observacion.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ObservacionPage implements ViewWillEnter {
  private readonly obsService = inject(ObservacionesService);
  private readonly fotos = inject(FotosService);
  private readonly catalogo = inject(CatalogoService);
  private readonly api = inject(ApiService);
  private readonly sb = inject(SupabaseService);
  private readonly nav = inject(NavController);
  private readonly router = inject(Router);
  private readonly alert = inject(AlertController);
  private readonly toast = inject(ToastController);

  readonly obs = signal<Observacion | null>(null);
  readonly url = signal<string | null>(null);
  readonly cargando = signal(true);
  readonly candidatos = signal<Especie[]>([]);
  readonly eligiendo = signal(false);
  readonly propia = computed(() => this.obs()?.usuario_id === this.sb.userId());
  readonly fechaCorta = fechaCorta;

  async ionViewWillEnter(): Promise<void> {
    const id = this.router.parseUrl(this.router.url).root.children['primary']?.segments[1]?.path;
    if (!id) return;
    this.cargando.set(true);
    try {
      const o = await this.obsService.una(id);
      this.obs.set(o);
      if (o) {
        const [urls, especies] = await Promise.all([
          this.fotos.urlsFirmadas([o.ruta_foto]),
          this.catalogo.porIds((o.ia_candidatos ?? []).map((c) => c.especie_id).filter((x): x is number => !!x)),
        ]);
        this.url.set(urls[o.ruta_foto] ?? null);
        this.candidatos.set(especies);
      }
    } catch {
      this.obs.set(null);
    } finally {
      this.cargando.set(false);
    }
  }

  volver(): void {
    this.nav.back();
  }

  async elegir(nombre: string): Promise<void> {
    const o = this.obs();
    if (!o || this.eligiendo()) return;
    this.eligiendo.set(true);
    try {
      const nueva = await this.api.elegir(o.id, nombre);
      this.obs.set({ ...o, ...nueva });
      this.catalogo.invalidar();
      void vibrarExito();
    } catch (e) {
      await this.avisar(e instanceof Error ? e.message : 'No se pudo guardar tu elección.');
    } finally {
      this.eligiendo.set(false);
    }
  }

  async cambiarPublica(evento: CustomEvent): Promise<void> {
    const o = this.obs();
    if (!o) return;
    const valor = !!evento.detail.checked;
    try {
      await this.obsService.cambiarPublica(o.id, valor);
      this.obs.set({ ...o, es_publica: valor });
    } catch {
      this.obs.set({ ...o });
      await this.avisar('No se pudo guardar el cambio.');
    }
  }

  async compartir(): Promise<void> {
    const o = this.obs();
    if (o) await compartirObservacion(o, this.toast);
  }

  async noEsCorrecto(): Promise<void> {
    const o = this.obs();
    if (!o) return;
    const a = await this.alert.create({
      header: '¿La especie no es correcta?',
      message: 'La observación pasará a revisión: podrás elegir entre las especies parecidas y un experto la revisará.',
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        {
          text: 'Mandar a revisión',
          handler: async () => {
            try {
              await this.obsService.marcarParaRevision(o.id);
              this.obs.set({ ...o, estado: 'revisar' });
            } catch {
              await this.avisar('No se pudo mandar a revisión. Intenta de nuevo.');
            }
          },
        },
      ],
    });
    await a.present();
  }

  async borrar(): Promise<void> {
    const o = this.obs();
    if (!o) return;
    const a = await this.alert.create({
      header: '¿Borrar esta observación?',
      message: 'Se borrarán la foto y el resultado. Ya contó para tu límite de hoy, así que borrarla no te devuelve la identificación.',
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        {
          text: 'Borrar',
          role: 'destructive',
          handler: async () => {
            try {
              await this.obsService.borrar(o);
              this.catalogo.invalidar();
              this.nav.navigateRoot('/app/coleccion');
            } catch {
              await this.avisar('No se pudo borrar. Intenta de nuevo.');
            }
          },
        },
      ],
    });
    await a.present();
  }

  private async avisar(mensaje: string): Promise<void> {
    await (await this.toast.create({ message: mensaje, duration: 3000, color: 'dark' })).present();
  }
}
