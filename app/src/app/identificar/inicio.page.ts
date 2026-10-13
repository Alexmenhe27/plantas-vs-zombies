import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonRefresher, IonRefresherContent, ToastController, ViewWillEnter } from '@ionic/angular';
import { environment } from '../../environments/environment';
import { fechaCorta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { GRUPOS } from '../core/grupos';
import { IdentificacionService } from '../core/identificacion.service';
import { Observacion } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { SupabaseService } from '../core/supabase.service';
import { FotoComponent } from '../shared/foto.component';

@Component({
  selector: 'app-inicio',
  imports: [FotoComponent, IonContent, IonIcon, IonRefresher, IonRefresherContent, RouterLink],
  templateUrl: './inicio.page.html',
  styleUrl: './inicio.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InicioPage implements ViewWillEnter {
  private readonly sb = inject(SupabaseService);
  private readonly fotos = inject(FotosService);
  private readonly obs = inject(ObservacionesService);
  private readonly identificacion = inject(IdentificacionService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastController);

  readonly grupos = GRUPOS;
  readonly limite = environment.limiteDiario;
  readonly restantes = signal<number | null>(null);
  readonly recientes = signal<Observacion[]>([]);
  readonly urls = signal<Record<string, string>>({});
  readonly procesando = signal(false);
  readonly nombre = computed(() => this.sb.perfil()?.nombre_usuario ?? '');
  readonly inicial = computed(() => (this.nombre() || this.sb.session()?.user.email || '?').charAt(0).toUpperCase());
  readonly usadoPct = computed(() => {
    const r = this.restantes();
    return r == null ? 0 : Math.round(((this.limite - r) / this.limite) * 100);
  });
  readonly saludo = saludoDelDia();
  readonly fechaCorta = fechaCorta;

  ionViewWillEnter(): void {
    void this.cargar();
  }

  async cargar(evento?: CustomEvent): Promise<void> {
    try {
      const [restantes, mias] = await Promise.all([this.obs.restantes(), this.obs.mias()]);
      this.restantes.set(restantes);
      const ultimas = mias.filter((o) => o.estado !== 'no_identificada').slice(0, 6);
      this.recientes.set(ultimas);
      this.urls.set(await this.fotos.urlsFirmadas(ultimas.map((o) => o.ruta_foto)));
    } catch {
      // Sin conexión: la pantalla sigue siendo usable.
    } finally {
      (evento?.target as HTMLIonRefresherElement | undefined)?.complete();
    }
  }

  async elegir(origen: 'camara' | 'galeria'): Promise<void> {
    if (this.procesando()) return;
    this.procesando.set(true);
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
      this.identificacion.poner(comprimida);
      await this.router.navigateByUrl('/analizando');
    } finally {
      this.procesando.set(false);
    }
  }

  private async avisar(mensaje: string): Promise<void> {
    const t = await this.toast.create({ message: mensaje, duration: 3500, color: 'dark' });
    await t.present();
  }

  nombreDe(o: Observacion): string {
    if (o.especie) return o.estado === 'revisar' ? `¿${o.especie.nombre_comun}?` : o.especie.nombre_comun;
    return o.ia_nombre_sugerido ?? 'Sin identificar';
  }
}

function saludoDelDia(hora = new Date().getHours()): string {
  if (hora < 12) return 'Buenos días';
  if (hora < 19) return 'Buenas tardes';
  return 'Buenas noches';
}
