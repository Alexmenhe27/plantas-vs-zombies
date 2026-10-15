import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { IonContent, IonIcon, NavController, ViewWillEnter } from '@ionic/angular';
import { CatalogoService } from '../core/catalogo.service';
import { fechaCorta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { estiloGrupo, etiquetaConservacion, iconoEspecie, nombreGrupo } from '../core/grupos';
import { IdentificacionService } from '../core/identificacion.service';
import { Avistamiento, Especie } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { FotoComponent } from '../shared/foto.component';
import { MapaComponent, PuntoMapa } from '../shared/mapa.component';

const TEXTO_NOM: Record<string, string> = {
  P: 'En peligro de extinción según la NOM-059-SEMARNAT.',
  A: 'Amenazada según la NOM-059-SEMARNAT.',
  Pr: 'Sujeta a protección especial según la NOM-059-SEMARNAT.',
  E: 'Probablemente extinta en el medio silvestre según la NOM-059-SEMARNAT.',
};

@Component({
  selector: 'app-ficha',
  imports: [FotoComponent, IonContent, IonIcon, MapaComponent, RouterLink],
  templateUrl: './ficha.page.html',
  styleUrl: './ficha.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FichaPage implements ViewWillEnter {
  private readonly catalogo = inject(CatalogoService);
  private readonly obs = inject(ObservacionesService);
  private readonly fotos = inject(FotosService);
  private readonly route = inject(ActivatedRoute);
  private readonly nav = inject(NavController);
  readonly identificacion = inject(IdentificacionService);

  readonly especie = signal<Especie | null>(null);
  readonly cargando = signal(true);
  readonly avistamientos = signal<Avistamiento[]>([]);
  readonly urls = signal<Record<string, { mini: string | null; completa: string | null }>>({});
  readonly portada = computed(() => {
    const a = this.avistamientos()[0];
    return this.especie()?.imagen_url ?? (a ? this.urls()[a.ruta_foto]?.completa : null) ?? null;
  });
  /** Crédito de la foto de referencia (Wikimedia Commons o iNaturalist). */
  readonly credito = computed(() => {
    const e = this.especie();
    if (!e?.imagen_url || !e.imagen_fuente) return null;
    return { url: e.imagen_fuente, sitio: e.imagen_fuente.includes('inaturalist') ? 'iNaturalist' : 'Wikimedia Commons' };
  });
  readonly conservacion = computed(() => (this.especie() ? etiquetaConservacion(this.especie()!) : null));
  readonly textoNom = computed(() => TEXTO_NOM[this.especie()?.categoria_nom059 ?? ''] ?? null);
  readonly estilo = computed(() => estiloGrupo(this.especie()));
  readonly puntos = computed<PuntoMapa[]>(() =>
    this.avistamientos()
      .filter((a) => a.latitud !== null && a.longitud !== null)
      .map((a) => ({
        id: a.id, latitud: a.latitud!, longitud: a.longitud!, titulo: a.nombre_usuario || 'Anónimo',
        subtitulo: fechaCorta(a.observada_en), reino: this.especie()?.reino ?? 'animal', grupo: this.especie()?.grupo ?? 'planta',
        enlace: ['/especie', a.especie_id],
      })),
  );

  readonly nombreGrupo = nombreGrupo;
  readonly fechaCorta = fechaCorta;
  readonly iconoEspecie = iconoEspecie;

  async ionViewWillEnter(): Promise<void> {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.cargando.set(true);
    try {
      const e = await this.catalogo.porId(id);
      this.especie.set(e);
      if (e) {
        const a = await this.obs.avistamientos(e.id, 30);
        this.avistamientos.set(a);
        this.urls.set(await this.fotos.urlsConMiniatura(a.map((x) => x.ruta_foto)));
      }
    } catch {
      // Sin conexión: se muestra lo que haya.
    } finally {
      this.cargando.set(false);
    }
  }

  volver(): void {
    this.nav.back();
  }
}
