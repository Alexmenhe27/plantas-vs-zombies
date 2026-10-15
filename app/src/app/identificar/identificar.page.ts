import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner, IonToggle, ToastController, ViewWillEnter } from '@ionic/angular';
import { tiempoHasta } from '../core/fechas';
import { IdentificacionService } from '../core/identificacion.service';
import { ObservacionesService } from '../core/observaciones.service';
import { SupabaseService } from '../core/supabase.service';
import { compartirObservacion } from '../shared/compartir';
import { FotoAnalisisComponent } from '../shared/foto-analisis.component';
import { ResultadoComponent } from '../shared/resultado/resultado.component';

/** Análisis y resultado en una sola pantalla: el nombre aparece en cuanto la IA lo escribe. */
@Component({
  selector: 'app-identificar',
  imports: [FotoAnalisisComponent, ResultadoComponent, IonContent, IonIcon, IonSpinner, IonToggle, RouterLink],
  templateUrl: './identificar.page.html',
  styleUrl: './identificar.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class IdentificarPage implements ViewWillEnter {
  readonly id = inject(IdentificacionService);
  readonly sb = inject(SupabaseService);
  private readonly obs = inject(ObservacionesService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastController);

  readonly observacion = computed(() => this.id.resultado()?.observacion ?? null);
  readonly esperar = computed(() => {
    const d = this.id.error()?.disponibleEn;
    return d ? tiempoHasta(d) : null;
  });
  readonly exito = computed(() => {
    const o = this.observacion();
    if (!o) return null;
    if (o.estado === 'identificada') return '¡Especie identificada!';
    if (o.estado === 'elegida') return '¡Guardada en tu colección!';
    return null;
  });
  readonly fasePantalla = computed(() => (this.id.fase() === 'listo' ? 'guardada' : this.id.fase()));

  ionViewWillEnter(): void {
    if (!this.id.foto()) {
      void this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
    }
  }

  cerrar(): void {
    this.id.limpiar();
    void this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
  }

  otra(): void {
    void this.id.empezar('camara');
  }

  async compartir(): Promise<void> {
    const o = this.observacion();
    if (o) await compartirObservacion(o, this.toast);
  }

  async cambiarPublica(evento: CustomEvent): Promise<void> {
    const o = this.observacion();
    if (!o) return;
    const valor = !!evento.detail.checked;
    try {
      await this.obs.cambiarPublica(o.id, valor);
      const r = this.id.resultado();
      if (r) this.id.resultado.set({ ...r, observacion: { ...r.observacion, es_publica: valor } });
    } catch {
      await (await this.toast.create({ message: 'No se pudo guardar el cambio.', duration: 2500, color: 'dark' })).present();
    }
  }
}
