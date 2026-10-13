import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner, NavController, ViewWillEnter } from '@ionic/angular';
import { CatalogoService } from '../core/catalogo.service';
import { fechaCorta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { etiquetaConservacion, iconoEspecie, nombreGrupo } from '../core/grupos';
import { Especie } from '../core/modelos';
import { Avistamiento, ObservacionesService } from '../core/observaciones.service';
import { FotoComponent } from '../shared/foto.component';

const TEXTO_NOM: Record<string, string> = {
  P: 'En peligro de extinción según la NOM-059-SEMARNAT.',
  A: 'Amenazada según la NOM-059-SEMARNAT.',
  Pr: 'Sujeta a protección especial según la NOM-059-SEMARNAT.',
  E: 'Probablemente extinta en el medio silvestre según la NOM-059-SEMARNAT.',
};

@Component({
  selector: 'app-ficha',
  imports: [FotoComponent, IonContent, IonIcon, IonSpinner, RouterLink],
  templateUrl: './ficha.page.html',
  styleUrl: './ficha.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FichaPage implements ViewWillEnter {
  readonly iconoEspecie = iconoEspecie;
  private readonly catalogo = inject(CatalogoService);
  private readonly obs = inject(ObservacionesService);
  private readonly fotos = inject(FotosService);
  private readonly route = inject(ActivatedRoute);
  private readonly nav = inject(NavController);

  readonly especie = signal<Especie | null>(null);
  readonly cargando = signal(true);
  readonly avistamientos = signal<Avistamiento[]>([]);
  readonly urls = signal<Record<string, string>>({});
  readonly portada = computed(() => {
    const a = this.avistamientos()[0];
    return this.especie()?.imagen_url ?? (a ? this.urls()[a.ruta_foto] : null) ?? null;
  });
  /** Crédito de la foto del catálogo (página del archivo en Wikimedia Commons). */
  readonly creditoFoto = computed(() => (this.especie()?.imagen_url ? this.especie()?.imagen_fuente ?? null : null));
  readonly conservacion = computed(() => (this.especie() ? etiquetaConservacion(this.especie()!) : null));
  readonly textoNom = computed(() => TEXTO_NOM[this.especie()?.categoria_nom059 ?? ''] ?? null);

  readonly nombreGrupo = nombreGrupo;
  readonly fechaCorta = fechaCorta;

  async ionViewWillEnter(): Promise<void> {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    try {
      const e = await this.catalogo.porId(id);
      this.especie.set(e ?? null);
      if (e) {
        const a = await this.obs.avistamientos(e.id);
        this.avistamientos.set(a);
        this.urls.set(await this.fotos.urlsFirmadas(a.map((x) => x.ruta_foto)));
      }
    } finally {
      this.cargando.set(false);
    }
  }

  volver(): void {
    this.nav.back();
  }
}
