import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  InfiniteScrollCustomEvent, IonContent, IonIcon, IonInfiniteScroll, IonInfiniteScrollContent, IonRefresher, IonRefresherContent, ViewWillEnter,
} from '@ionic/angular';
import { fechaCorta, seccionHistorial } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { GRUPOS, estiloGrupo, iconoEspecie, nombreEstado, porcentaje } from '../core/grupos';
import { EspecieColeccion, Observacion } from '../core/modelos';
import { ObservacionesService, POR_PAGINA_OBS } from '../core/observaciones.service';
import { SupabaseService } from '../core/supabase.service';
import { FotoComponent } from '../shared/foto.component';
import { MapaComponent, PuntoMapa } from '../shared/mapa.component';
import { TarjetaEspecieComponent } from '../shared/tarjeta-especie.component';

type Vista = 'especies' | 'observaciones' | 'mapa';

@Component({
  selector: 'app-coleccion',
  imports: [
    FotoComponent, IonContent, IonIcon, IonInfiniteScroll, IonInfiniteScrollContent, IonRefresher, IonRefresherContent, MapaComponent,
    RouterLink, TarjetaEspecieComponent,
  ],
  templateUrl: './coleccion.page.html',
  styleUrl: './coleccion.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ColeccionPage implements ViewWillEnter {
  readonly sb = inject(SupabaseService);
  private readonly obsService = inject(ObservacionesService);
  private readonly fotos = inject(FotosService);
  private readonly route = inject(ActivatedRoute);

  readonly vista = signal<Vista>('especies');
  readonly coleccion = signal<EspecieColeccion[] | null>(null);
  readonly observaciones = signal<Observacion[]>([]);
  readonly hayMas = signal(false);
  readonly urls = signal<Record<string, { mini: string | null; completa: string | null }>>({});
  readonly puntos = signal<PuntoMapa[] | null>(null);
  readonly error = signal(false);
  readonly grupoFiltro = signal<string | null>(null);

  readonly stats = computed(() => {
    const c = this.coleccion() ?? [];
    return {
      especies: c.length,
      observaciones: c.reduce((s, x) => s + x.veces, 0),
      protegidas: c.filter((x) => x.especie.protegida).length,
    };
  });
  readonly porGrupo = computed(() =>
    GRUPOS.map((g) => ({ ...g, total: (this.coleccion() ?? []).filter((x) => g.incluye(x.especie)).length })),
  );
  readonly especiesFiltradas = computed(() => {
    const g = GRUPOS.find((x) => x.id === this.grupoFiltro());
    return (this.coleccion() ?? []).filter((x) => !g || g.incluye(x.especie));
  });
  readonly secciones = computed(() => {
    const mapa = new Map<string, Observacion[]>();
    for (const o of this.observaciones()) {
      const s = seccionHistorial(o.observada_en);
      mapa.set(s, [...(mapa.get(s) ?? []), o]);
    }
    return [...mapa.entries()].map(([titulo, items]) => ({ titulo, items }));
  });

  readonly fechaCorta = fechaCorta;
  readonly porcentaje = porcentaje;
  readonly estiloGrupo = estiloGrupo;
  readonly iconoEspecie = iconoEspecie;
  readonly nombreEstado = nombreEstado;

  ionViewWillEnter(): void {
    const v = this.route.snapshot.queryParamMap.get('vista') as Vista | null;
    if (v) this.vista.set(v);
    void this.cargar();
  }

  async cargar(evento?: CustomEvent): Promise<void> {
    this.error.set(false);
    try {
      const [coleccion, obs] = await Promise.all([this.obsService.coleccion(), this.obsService.mias(0)]);
      this.coleccion.set(coleccion);
      this.observaciones.set(obs);
      this.hayMas.set(obs.length === POR_PAGINA_OBS);
      await this.firmar([...coleccion.map((c) => c.ruta_foto), ...obs.map((o) => o.ruta_foto)]);
      if (this.vista() === 'mapa') await this.cargarMapa();
    } catch {
      this.error.set(true);
      if (this.coleccion() === null) this.coleccion.set([]);
    } finally {
      (evento?.target as HTMLIonRefresherElement | undefined)?.complete();
    }
  }

  async masObservaciones(evento: InfiniteScrollCustomEvent): Promise<void> {
    try {
      const mas = await this.obsService.mias(this.observaciones().length);
      this.observaciones.update((l) => [...l, ...mas]);
      this.hayMas.set(mas.length === POR_PAGINA_OBS);
      await this.firmar(mas.map((o) => o.ruta_foto));
    } finally {
      await evento.target.complete();
    }
  }

  cambiarVista(v: Vista): void {
    this.vista.set(v);
    if (v === 'mapa' && this.puntos() === null) void this.cargarMapa();
  }

  nombre(o: Observacion): string {
    if (o.especie && o.estado !== 'revisar') return o.especie.nombre_comun;
    if (o.estado === 'no_identificada') return 'Foto sin resultado';
    return o.especie ? `¿${o.especie.nombre_comun}?` : 'Por confirmar';
  }

  private async cargarMapa(): Promise<void> {
    const con = await this.obsService.miasConUbicacion();
    this.puntos.set(
      con
        .filter((o) => o.especie && o.latitud !== null && o.longitud !== null)
        .map((o) => ({
          id: o.id, latitud: o.latitud!, longitud: o.longitud!, titulo: o.especie!.nombre_comun, subtitulo: fechaCorta(o.observada_en),
          reino: o.especie!.reino, grupo: o.especie!.grupo, enlace: ['/observacion', o.id],
        })),
    );
  }

  private async firmar(rutas: string[]): Promise<void> {
    const nuevas = await this.fotos.urlsConMiniatura(rutas);
    this.urls.update((u) => ({ ...u, ...nuevas }));
  }
}
