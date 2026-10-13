import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AlertController, IonContent, IonIcon, IonSpinner, IonToggle, NavController, ToastController, ViewWillEnter } from '@ionic/angular';
import { CatalogoService } from '../core/catalogo.service';
import { fechaCorta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { etiquetaConservacion, iconoEspecie, nivelConfianza, nombreGrupo, porcentaje } from '../core/grupos';
import { Especie, Observacion } from '../core/modelos';
import { ObservacionesService } from '../core/observaciones.service';
import { FotoComponent } from '../shared/foto.component';

type Vista = 'identificada' | 'revisar' | 'borrosa' | 'sin_organismo';

interface CandidatoVista {
  especie: Especie | null;
  cientifico: string;
  comun: string | null;
  confianza: number;
}

@Component({
  selector: 'app-observacion',
  imports: [FotoComponent, IonContent, IonIcon, IonSpinner, IonToggle, RouterLink],
  templateUrl: './observacion.page.html',
  styleUrl: './observacion.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ObservacionPage implements ViewWillEnter {
  private readonly obsService = inject(ObservacionesService);
  private readonly fotos = inject(FotosService);
  private readonly catalogo = inject(CatalogoService);
  private readonly nav = inject(NavController);
  private readonly router = inject(Router);
  private readonly alert = inject(AlertController);
  private readonly toast = inject(ToastController);

  readonly obs = signal<Observacion | null>(null);
  readonly url = signal<string | null>(null);
  readonly cargando = signal(true);
  readonly candidatos = signal<CandidatoVista[]>([]);
  readonly nueva = signal(false);

  readonly especie = computed(() => this.obs()?.especie ?? null);
  readonly vista = computed<Vista | null>(() => {
    const o = this.obs();
    if (!o) return null;
    if (o.ia_problema === 'borrosa') return 'borrosa';
    if (o.ia_problema === 'sin_organismo') return 'sin_organismo';
    if (o.estado === 'revisar' || !o.especie) return 'revisar';
    return 'identificada';
  });
  readonly conservacion = computed(() => (this.especie() ? etiquetaConservacion(this.especie()!) : null));

  readonly porcentaje = porcentaje;
  readonly nivelConfianza = nivelConfianza;
  readonly nombreGrupo = nombreGrupo;
  readonly iconoEspecie = iconoEspecie;
  readonly fechaCorta = fechaCorta;

  async ionViewWillEnter(): Promise<void> {
    const url = this.router.parseUrl(this.router.url);
    const id = url.root.children['primary']?.segments[1]?.path;
    this.nueva.set(url.queryParams['nueva'] === '1');
    if (!id) return;
    this.cargando.set(true);
    try {
      const o = await this.obsService.una(id);
      this.obs.set(o);
      if (o) {
        const urls = await this.fotos.urlsFirmadas([o.ruta_foto]);
        this.url.set(urls[o.ruta_foto] ?? null);
        let especies = await this.catalogo.cargar();
        if ((o.ia_candidatos ?? []).some((c) => c.especie_id && !especies.some((e) => e.id === c.especie_id))) {
          especies = await this.catalogo.cargar(true); // hay especies recién agregadas
        }
        const lista: CandidatoVista[] = (o.ia_candidatos ?? []).map((c) => {
          const especie = especies.find((e) => e.id === c.especie_id) ?? null;
          return { especie, cientifico: c.nombre_cientifico ?? especie?.nombre_cientifico ?? '', comun: c.nombre_comun ?? especie?.nombre_comun ?? null, confianza: c.confianza };
        }).filter((c) => !!c.cientifico);
        // Si la IA no dio candidatos pero sí una especie probable, se muestra esa.
        if (!lista.length && o.especie) lista.push({ especie: o.especie, cientifico: o.especie.nombre_cientifico, comun: o.especie.nombre_comun, confianza: o.ia_confianza ?? 0 });
        this.candidatos.set(lista);
      }
    } finally {
      this.cargando.set(false);
    }
  }

  volver(): void {
    if (this.nueva()) this.nav.navigateRoot('/app/identificar');
    else this.nav.back();
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
      await (await this.toast.create({ message: 'No se pudo guardar el cambio.', duration: 2500, color: 'dark' })).present();
    }
  }

  async borrar(): Promise<void> {
    const o = this.obs();
    if (!o) return;
    const a = await this.alert.create({
      header: '¿Borrar esta observación?',
      message: 'Se borrará la foto y el resultado. No cuenta de nuevo para tu límite de hoy.',
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        {
          text: 'Borrar',
          role: 'destructive',
          handler: async () => {
            await this.obsService.borrar(o);
            this.nav.navigateRoot('/app/historial');
          },
        },
      ],
    });
    await a.present();
  }
}
