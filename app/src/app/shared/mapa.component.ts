import {
  ChangeDetectionStrategy, Component, ElementRef, OnDestroy, afterNextRender, computed, effect, inject, input, signal, viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonIcon } from '@ionic/angular';
import type { FeatureCollection } from 'geojson';
import type { GeoJSONSource, Map as MapaLibre, MapLayerMouseEvent } from 'maplibre-gl';
import { COLOR_GRUPO_MAPA, colorGrupo, estiloGrupo, nombreGrupo } from '../core/grupos';
import { TemaService } from '../core/tema.service';

export interface PuntoMapa {
  id: string;
  latitud: number;
  longitud: number;
  titulo: string;
  subtitulo?: string;
  reino: string;
  grupo: string;
  /** A dónde lleva la tarjeta al tocar el punto. */
  enlace: unknown[];
}

// Mapas gratuitos de OpenStreetMap (OpenFreeMap: sin clave ni límite de uso).
const ESTILOS = { claro: 'https://tiles.openfreemap.org/styles/positron', oscuro: 'https://tiles.openfreemap.org/styles/dark' };
let cssCargado = false;

/**
 * Mapa con MapLibre. La librería (unos 200 KB) se descarga solo cuando se abre un mapa.
 * Los puntos cercanos se agrupan; con `aproximados` cada punto muestra un círculo de ~5 km (la ubicación pública
 * se redondea para proteger la privacidad).
 */
@Component({
  selector: 'app-mapa',
  imports: [IonIcon, RouterLink],
  template: `
    <div class="lienzo" #lienzo [style.height]="altura()"></div>
    @if (estado() === 'cargando') { <div class="capa esqueleto"></div> }
    @if (estado() === 'error') {
      <div class="capa aviso-mapa"><ion-icon name="cloud-offline-outline" /><span>No se pudo cargar el mapa. Revisa tu conexión.</span></div>
    }
    @if (estado() === 'listo' && !puntos().length) {
      <div class="vacio-mapa"><span>{{ textoVacio() }}</span></div>
    }
    @if (seleccion(); as p) {
      <a class="seleccion aparece" [routerLink]="p.enlace" [style]="estilo(p)">
        <span class="punto"></span>
        <span class="textos"><strong>{{ p.titulo }}</strong>@if (p.subtitulo) { <small>{{ p.subtitulo }}</small> }</span>
        <span class="chip grupo">{{ nombreGrupo(p.grupo) }}</span>
        <ion-icon name="chevron-forward" />
      </a>
    }
  `,
  styles: `
    :host { display: block; position: relative; border-radius: var(--radio-l); overflow: hidden; background: var(--c-superficie-2); border: 1px solid var(--c-borde); }
    .lienzo { width: 100%; }
    .capa { position: absolute; inset: 0; border-radius: 0; }
    .aviso-mapa { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--c-texto-2); font-size: 14px; text-align: center; padding: 20px; }
    .aviso-mapa ion-icon { font-size: 30px; }
    .vacio-mapa { position: absolute; left: 12px; right: 12px; top: 12px; display: flex; justify-content: center; pointer-events: none; }
    .vacio-mapa span { background: var(--c-superficie); color: var(--c-texto-2); padding: 8px 12px; border-radius: 999px; font-size: 13px; font-weight: 700; box-shadow: var(--sombra-2); }
    .seleccion {
      position: absolute; left: 10px; right: 10px; bottom: 10px; display: flex; align-items: center; gap: 10px;
      padding: 12px 14px; border-radius: var(--radio-m); background: var(--c-superficie); color: var(--c-texto);
      text-decoration: none; box-shadow: var(--sombra-3);
    }
    .punto { width: 12px; height: 12px; border-radius: 50%; background: var(--grupo); flex: none; }
    .textos { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .textos strong { font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .textos small { font-size: 12.5px; color: var(--c-texto-2); }
    .seleccion > ion-icon { color: var(--c-texto-3); flex: none; }
    :host ::ng-deep .maplibregl-ctrl-attrib { font-size: 10px; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MapaComponent implements OnDestroy {
  readonly puntos = input<PuntoMapa[]>([]);
  readonly aproximados = input(false);
  readonly altura = input('340px');
  readonly textoVacio = input('Todavía no hay avistamientos con ubicación.');

  private readonly tema = inject(TemaService);
  private readonly lienzo = viewChild.required<ElementRef<HTMLDivElement>>('lienzo');
  readonly estado = signal<'cargando' | 'listo' | 'error'>('cargando');
  readonly seleccion = signal<PuntoMapa | null>(null);
  readonly nombreGrupo = nombreGrupo;
  private mapa: MapaLibre | null = null;
  private readonly porId = computed(() => new Map(this.puntos().map((p) => [p.id, p])));

  constructor() {
    afterNextRender(() => void this.crear());
    effect(() => {
      this.puntos();
      this.aproximados();
      this.pintarDatos();
    });
    effect(() => {
      const oscuro = this.tema.oscuro();
      if (this.mapa) {
        this.mapa.setStyle(oscuro ? ESTILOS.oscuro : ESTILOS.claro);
        this.mapa.once('style.load', () => this.agregarCapas());
      }
    });
  }

  estilo(p: PuntoMapa): Record<string, string> {
    return estiloGrupo({ reino: p.reino as 'animal' | 'planta', grupo: p.grupo });
  }

  private async crear(): Promise<void> {
    try {
      if (!cssCargado) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'maplibre/maplibre-gl.css';
        document.head.appendChild(link);
        cssCargado = true;
      }
      const maplibre = await import('maplibre-gl');
      maplibre.setWorkerUrl(new URL('maplibre/maplibre-gl-worker.mjs', document.baseURI).href);
      this.mapa = new maplibre.Map({
        container: this.lienzo().nativeElement,
        style: this.tema.oscuro() ? ESTILOS.oscuro : ESTILOS.claro,
        center: [-99.1, 19.4],
        zoom: 4,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
      });
      this.mapa.touchZoomRotate.disableRotation();
      this.escucharToques(this.mapa);
      this.mapa.once('style.load', () => {
        this.agregarCapas();
        this.encuadrar();
        this.estado.set('listo');
      });
      this.mapa.on('error', (e) => {
        if (this.estado() === 'cargando') this.estado.set('error');
        console.warn('Mapa:', e.error?.message);
      });
    } catch {
      this.estado.set('error');
    }
  }

  private datos(): FeatureCollection {
    const oscuro = this.tema.oscuro() ? 1 : 0;
    return {
      type: 'FeatureCollection',
      features: this.puntos().map((p) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [p.longitud, p.latitud] },
        properties: { id: p.id, color: COLOR_GRUPO_MAPA[colorGrupo({ reino: p.reino as 'animal' | 'planta', grupo: p.grupo })][oscuro] },
      })),
    };
  }

  private agregarCapas(): void {
    const m = this.mapa;
    if (!m || m.getSource('puntos')) return;
    const fondo = this.tema.oscuro() ? '#151d19' : '#ffffff';
    m.addSource('puntos', { type: 'geojson', data: this.datos(), cluster: true, clusterRadius: 42, clusterMaxZoom: 11 });
    if (this.aproximados()) {
      // Círculo de ~5 km (la ubicación pública se redondea a ~10 km).
      m.addLayer({
        id: 'halo', type: 'circle', source: 'puntos', filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': ['get', 'color'], 'circle-opacity': 0.16, 'circle-stroke-width': 1.5,
          'circle-stroke-color': ['get', 'color'], 'circle-stroke-opacity': 0.45,
          'circle-radius': ['interpolate', ['exponential', 2], ['zoom'], 5, 3, 12, 190],
        },
      });
    }
    m.addLayer({
      id: 'grupos', type: 'circle', source: 'puntos', filter: ['has', 'point_count'],
      paint: {
        'circle-color': this.tema.oscuro() ? '#5ec79b' : '#1f6b4f', 'circle-opacity': 0.92,
        'circle-radius': ['step', ['get', 'point_count'], 16, 10, 21, 50, 27],
        'circle-stroke-width': 3, 'circle-stroke-color': fondo,
      },
    });
    m.addLayer({
      id: 'grupos-numero', type: 'symbol', source: 'puntos', filter: ['has', 'point_count'],
      layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 13, 'text-font': ['Noto Sans Bold'] },
      paint: { 'text-color': this.tema.oscuro() ? '#062319' : '#ffffff' },
    });
    m.addLayer({
      id: 'punto', type: 'circle', source: 'puntos', filter: ['!', ['has', 'point_count']],
      paint: { 'circle-color': ['get', 'color'], 'circle-radius': 8, 'circle-stroke-width': 3, 'circle-stroke-color': fondo },
    });
  }

  /** Toques sobre los puntos (se registran una vez: siguen valiendo cuando cambia el estilo claro/oscuro). */
  private escucharToques(m: MapaLibre): void {
    m.on('click', 'punto', (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.['id'] as string | undefined;
      this.seleccion.set(id ? this.porId().get(id) ?? null : null);
    });
    m.on('click', 'grupos', async (e: MapLayerMouseEvent) => {
      const f = e.features?.[0];
      const fuente = m.getSource('puntos') as GeoJSONSource;
      if (!f || f.geometry.type !== 'Point') return;
      const zoom = await fuente.getClusterExpansionZoom(f.properties?.['cluster_id'] as number);
      m.easeTo({ center: f.geometry.coordinates as [number, number], zoom });
    });
    for (const capa of ['punto', 'grupos']) {
      m.on('mouseenter', capa, () => (m.getCanvas().style.cursor = 'pointer'));
      m.on('mouseleave', capa, () => (m.getCanvas().style.cursor = ''));
    }
  }

  private pintarDatos(): void {
    const fuente = this.mapa?.getSource('puntos') as GeoJSONSource | undefined;
    if (!fuente) return;
    fuente.setData(this.datos());
    this.seleccion.set(null);
    this.encuadrar();
  }

  private encuadrar(): void {
    const pts = this.puntos();
    if (!this.mapa || !pts.length) return;
    if (pts.length === 1) {
      this.mapa.jumpTo({ center: [pts[0].longitud, pts[0].latitud], zoom: this.aproximados() ? 8 : 12 });
      return;
    }
    const lons = pts.map((p) => p.longitud);
    const lats = pts.map((p) => p.latitud);
    this.mapa.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: 50, maxZoom: this.aproximados() ? 9 : 13, duration: 0 });
  }

  ngOnDestroy(): void {
    this.mapa?.remove();
    this.mapa = null;
  }
}
