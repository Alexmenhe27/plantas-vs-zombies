import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { InfiniteScrollCustomEvent, IonContent, IonIcon, IonInfiniteScroll, IonInfiniteScrollContent, ViewWillEnter } from '@ionic/angular';
import { CatalogoService, POR_PAGINA } from '../core/catalogo.service';
import { fechaCorta } from '../core/fechas';
import { GRUPOS, estiloGrupo } from '../core/grupos';
import { EspecieResumen } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { MapaComponent, PuntoMapa } from '../shared/mapa.component';
import { TarjetaEspecieComponent } from '../shared/tarjeta-especie.component';

@Component({
  selector: 'app-catalogo',
  imports: [IonContent, IonIcon, IonInfiniteScroll, IonInfiniteScrollContent, MapaComponent, TarjetaEspecieComponent],
  templateUrl: './catalogo.page.html',
  styleUrl: './catalogo.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogoPage implements ViewWillEnter {
  private readonly catalogo = inject(CatalogoService);
  private readonly obs = inject(ObservacionesService);
  private readonly route = inject(ActivatedRoute);

  readonly grupos = GRUPOS;
  readonly estiloGrupo = estiloGrupo;
  readonly vista = signal<'lista' | 'mapa'>('lista');
  readonly grupo = signal<string | null>(null);
  readonly soloProtegidas = signal(false);
  readonly busqueda = signal('');
  readonly especies = signal<EspecieResumen[]>([]);
  readonly total = signal<number | null>(null);
  readonly cargando = signal(true);
  readonly error = signal(false);
  readonly hayMas = signal(false);
  readonly puntos = signal<PuntoMapa[] | null>(null);
  readonly hayFiltros = computed(() => !!this.grupo() || this.soloProtegidas() || !!this.busqueda().trim());
  private consulta = 0;
  private espera: ReturnType<typeof setTimeout> | null = null;
  private versionCargada = -1;

  ionViewWillEnter(): void {
    const g = this.route.snapshot.queryParamMap.get('grupo');
    if (g && g !== this.grupo()) {
      this.grupo.set(g);
      void this.recargar();
    } else if (this.versionCargada !== this.catalogo.version()) {
      void this.recargar();
    }
  }

  async recargar(): Promise<void> {
    const n = ++this.consulta;
    this.cargando.set(true);
    this.error.set(false);
    try {
      const r = await this.catalogo.buscar(this.filtro(), 0);
      if (n !== this.consulta) return;
      this.especies.set(r.especies);
      this.total.set(r.total);
      this.hayMas.set(r.especies.length === POR_PAGINA);
      this.versionCargada = this.catalogo.version();
    } catch {
      if (n === this.consulta) this.error.set(true);
    } finally {
      if (n === this.consulta) this.cargando.set(false);
    }
  }

  async masEspecies(evento: InfiniteScrollCustomEvent): Promise<void> {
    const n = this.consulta;
    try {
      const r = await this.catalogo.buscar(this.filtro(), this.especies().length);
      if (n === this.consulta) {
        this.especies.update((l) => [...l, ...r.especies]);
        this.hayMas.set(r.especies.length === POR_PAGINA);
      }
    } finally {
      await evento.target.complete();
    }
  }

  buscar(evento: Event): void {
    this.busqueda.set((evento.target as HTMLInputElement).value);
    if (this.espera) clearTimeout(this.espera);
    this.espera = setTimeout(() => void this.recargar(), 250);
  }

  elegirGrupo(id: string | null): void {
    this.grupo.set(this.grupo() === id ? null : id);
    void this.recargar();
    if (this.vista() === 'mapa') void this.cargarMapa();
  }

  cambiarProtegidas(): void {
    this.soloProtegidas.update((v) => !v);
    void this.recargar();
  }

  limpiar(): void {
    this.busqueda.set('');
    this.grupo.set(null);
    this.soloProtegidas.set(false);
    void this.recargar();
  }

  verMapa(): void {
    this.vista.set('mapa');
    void this.cargarMapa();
  }

  private async cargarMapa(): Promise<void> {
    const avistamientos = await this.obs.avistamientos(null, 300);
    const g = GRUPOS.find((x) => x.id === this.grupo());
    this.puntos.set(
      avistamientos
        .filter((a) => a.latitud !== null && a.longitud !== null && (!g || g.incluye(a)))
        .map((a) => ({
          id: a.id, latitud: a.latitud!, longitud: a.longitud!, titulo: a.nombre_comun,
          subtitulo: `${fechaCorta(a.observada_en)} · ${a.nombre_usuario || 'Anónimo'}`,
          reino: a.reino, grupo: a.grupo, enlace: ['/especie', a.especie_id],
        })),
    );
  }

  private filtro() {
    return { texto: this.busqueda(), grupo: this.grupo(), soloProtegidas: this.soloProtegidas() };
  }
}
