import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonRefresher, IonRefresherContent, IonSpinner, ViewWillEnter } from '@ionic/angular';
import { CupoService } from '../core/cupo.service';
import { fechaCorta, tiempoHasta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { GRUPOS, estiloGrupo, iconoEspecie } from '../core/grupos';
import { IdentificacionService } from '../core/identificacion.service';
import { Observacion } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { PendientesService } from '../core/pendientes.service';
import { SupabaseService } from '../core/supabase.service';
import { FotoComponent } from '../shared/foto.component';

@Component({
  selector: 'app-inicio',
  imports: [FotoComponent, IonContent, IonIcon, IonRefresher, IonRefresherContent, IonSpinner, RouterLink],
  templateUrl: './inicio.page.html',
  styleUrl: './inicio.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InicioPage implements ViewWillEnter {
  readonly sb = inject(SupabaseService);
  readonly identificacion = inject(IdentificacionService);
  readonly pendientes = inject(PendientesService);
  private readonly cupoService = inject(CupoService);
  private readonly fotos = inject(FotosService);
  private readonly obs = inject(ObservacionesService);

  readonly grupos = GRUPOS;
  readonly cupo = this.cupoService.cupo;
  readonly recientes = signal<Observacion[] | null>(null);
  readonly urls = signal<Record<string, { mini: string | null; completa: string | null }>>({});
  readonly nombre = computed(() => this.sb.perfil()?.nombre_usuario ?? '');
  readonly inicial = computed(() => (this.nombre() || this.sb.session()?.user.email || '?').charAt(0).toUpperCase());
  readonly usadoPct = computed(() => {
    const c = this.cupo();
    return c ? Math.round(((c.limite - c.restantes) / Math.max(1, c.limite)) * 100) : 0;
  });
  readonly esperar = computed(() => {
    const d = this.cupo()?.disponible_en;
    return d ? tiempoHasta(d) : null;
  });
  readonly saludo = saludoDelDia();
  readonly fechaCorta = fechaCorta;
  readonly estiloGrupo = estiloGrupo;
  readonly iconoEspecie = iconoEspecie;

  ionViewWillEnter(): void {
    void this.cargar();
  }

  async cargar(evento?: CustomEvent): Promise<void> {
    try {
      const [, mias] = await Promise.all([this.cupoService.actualizar(), this.obs.mias(0, 12), this.pendientes.cargar()]);
      const ultimas = mias.filter((o) => o.especie && o.estado !== 'no_identificada').slice(0, 8);
      this.recientes.set(ultimas);
      this.urls.set(await this.fotos.urlsConMiniatura(ultimas.map((o) => o.ruta_foto)));
      void this.pendientes.procesar();
    } catch {
      // Sin conexión: la pantalla sigue siendo usable.
      if (this.recientes() === null) this.recientes.set([]);
    } finally {
      (evento?.target as HTMLIonRefresherElement | undefined)?.complete();
    }
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
