import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonContent, IonRefresher, IonRefresherContent, IonSpinner, ViewWillEnter } from '@ionic/angular';
import { fechaCorta, seccionHistorial } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { GRUPOS, porcentaje } from '../core/grupos';
import { Observacion } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { FotoComponent } from '../shared/foto.component';

@Component({
  selector: 'app-historial',
  imports: [FotoComponent, IonContent, IonRefresher, IonRefresherContent, IonSpinner, RouterLink],
  templateUrl: './historial.page.html',
  styleUrl: './historial.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HistorialPage implements ViewWillEnter {
  private readonly obsService = inject(ObservacionesService);
  private readonly fotos = inject(FotosService);

  readonly todas = signal<Observacion[]>([]);
  readonly urls = signal<Record<string, string>>({});
  readonly cargando = signal(true);
  readonly error = signal(false);
  readonly filtro = signal<string>('todos');

  /** Las fotos que no sirvieron no se muestran en el historial. */
  readonly validas = computed(() => this.todas().filter((o) => o.estado !== 'no_identificada' || !o.ia_problema));
  readonly stats = computed(() => {
    const conEspecie = this.validas().filter((o) => o.especie && o.estado !== 'revisar');
    return {
      observaciones: this.validas().length,
      especies: new Set(conEspecie.map((o) => o.especie!.id)).size,
      protegidas: new Set(conEspecie.filter((o) => o.especie!.protegida).map((o) => o.especie!.id)).size,
    };
  });
  readonly chips = computed(() =>
    GRUPOS.map((g) => ({ ...g, total: this.validas().filter((o) => o.especie && g.incluye(o.especie)).length })).filter((g) => g.total > 0),
  );
  readonly secciones = computed(() => {
    const g = GRUPOS.find((x) => x.id === this.filtro());
    const lista = g ? this.validas().filter((o) => o.especie && g.incluye(o.especie)) : this.validas();
    const mapa = new Map<string, Observacion[]>();
    for (const o of lista) {
      const s = seccionHistorial(o.creado_en);
      mapa.set(s, [...(mapa.get(s) ?? []), o]);
    }
    return [...mapa.entries()].map(([titulo, items]) => ({ titulo, items }));
  });

  readonly fechaCorta = fechaCorta;
  readonly porcentaje = porcentaje;

  ionViewWillEnter(): void {
    void this.cargar();
  }

  async cargar(evento?: CustomEvent): Promise<void> {
    this.error.set(false);
    try {
      const lista = await this.obsService.mias();
      this.todas.set(lista);
      this.urls.set(await this.fotos.urlsFirmadas(lista.map((o) => o.ruta_foto)));
    } catch {
      this.error.set(true);
    } finally {
      this.cargando.set(false);
      (evento?.target as HTMLIonRefresherElement | undefined)?.complete();
    }
  }

  nombre(o: Observacion): string {
    if (o.especie) return o.estado === 'revisar' ? `¿${o.especie.nombre_comun}?` : o.especie.nombre_comun;
    return o.ia_nombre_sugerido ?? 'Sin identificar';
  }
}
