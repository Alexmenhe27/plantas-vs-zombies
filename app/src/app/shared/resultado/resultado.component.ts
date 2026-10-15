import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonIcon, IonSpinner } from '@ionic/angular';
import {
  estiloGrupo, etiquetaConservacion, iconoEspecie, nivelConfianza, nombreGrupo, porcentaje, reinoDeGrupo,
} from '../../core/grupos';
import { Especie, Observacion, Parcial, Reino } from '../../core/modelos';
import { WikipediaService } from '../../core/wikipedia.service';
import { FotoComponent } from '../foto.component';

export interface CandidatoVista {
  cientifico: string;
  comun: string | null;
  confianza: number;
  especie: Especie | null;
  grupo: string | null;
}

const CONSEJOS = [
  'México es uno de los cinco países con más especies del mundo.',
  'Las fotos con buena luz y de cerca se identifican mejor.',
  'Tus observaciones son privadas, salvo que tú decidas publicarlas.',
  'Si la IA duda, podrás elegir entre las especies más parecidas.',
  'En lo público, la ubicación siempre es aproximada para cuidar tu privacidad.',
];

const TEXTO_NOM: Record<string, string> = {
  P: 'En peligro de extinción según la NOM-059-SEMARNAT.',
  A: 'Amenazada según la NOM-059-SEMARNAT.',
  Pr: 'Sujeta a protección especial según la NOM-059-SEMARNAT.',
  E: 'Probablemente extinta en el medio silvestre según la NOM-059-SEMARNAT.',
};

/** Panel del resultado de una identificación: mientras llega (por partes) y ya guardado. */
@Component({
  selector: 'app-resultado',
  imports: [FotoComponent, IonIcon, IonSpinner, RouterLink],
  templateUrl: './resultado.component.html',
  styleUrl: './resultado.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResultadoComponent {
  private readonly wikipedia = inject(WikipediaService);

  readonly parcial = input<Parcial>({});
  readonly observacion = input<Observacion | null>(null);
  readonly candidatosEspecies = input<Especie[]>([]);
  readonly fichaPendiente = input(false);
  /** La persona puede elegir entre las parecidas (es su observación y está en revisión). */
  readonly puedeElegir = input(false);
  readonly eligiendo = input(false);
  readonly elegir = output<string>();

  readonly nombreGrupo = nombreGrupo;
  readonly porcentaje = porcentaje;
  readonly nivelConfianza = nivelConfianza;
  readonly iconoEspecie = iconoEspecie;
  readonly consejo = signal(CONSEJOS[Math.floor(Math.random() * CONSEJOS.length)]);
  readonly elegido = signal<string | null>(null);
  private readonly fotosWiki = signal<Record<string, string | null>>({});

  readonly especie = computed(() => this.observacion()?.especie ?? null);
  /** Lo que se muestra mientras todavía no hay observación guardada. */
  readonly nombreComun = computed(() => this.especie()?.nombre_comun ?? this.parcial().nombre_comun ?? null);
  readonly nombreCientifico = computed(() => this.especie()?.nombre_cientifico ?? this.parcial().nombre_cientifico ?? null);
  readonly confianza = computed(() => this.observacion()?.ia_confianza ?? this.parcial().confianza ?? null);
  readonly explicacion = computed(() => this.observacion()?.ia_explicacion ?? this.parcial().explicacion ?? null);
  readonly grupoVista = computed(() => {
    const e = this.especie();
    if (e) return { reino: e.reino, grupo: e.grupo };
    const p = this.parcial();
    return p.grupo ? { reino: (p.reino ?? 'animal') as Reino, grupo: p.grupo } : null;
  });
  readonly estilo = computed(() => estiloGrupo(this.grupoVista()));
  readonly problema = computed(() => this.observacion()?.ia_problema ?? (this.parcial().problema !== 'ninguno' ? this.parcial().problema : null) ?? null);

  /** identificada · revisar · elegida · corregida · no_identificada · o "llegando" mientras no hay observación. */
  readonly vista = computed(() => {
    const o = this.observacion();
    if (!o) return this.problema() ? 'problema' : this.nombreComun() ? 'llegando' : 'esperando';
    if (o.ia_problema || o.estado === 'no_identificada') return 'problema';
    if (o.estado === 'revisar' || !o.especie) return 'revisar';
    return o.estado;
  });
  readonly conservacion = computed(() => (this.especie() ? etiquetaConservacion(this.especie()!) : null));
  readonly textoNom = computed(() => TEXTO_NOM[this.especie()?.categoria_nom059 ?? ''] ?? null);
  readonly tonoConfianza = computed(() => {
    const c = this.confianza() ?? 0;
    return c >= 0.7 ? 'alta' : c >= 0.5 ? 'media' : 'baja';
  });

  readonly candidatos = computed<CandidatoVista[]>(() => {
    const o = this.observacion();
    if (!o) return [];
    const especies = new Map(this.candidatosEspecies().map((e) => [e.id, e]));
    const lista = (o.ia_candidatos ?? [])
      .map((c) => {
        const especie = (c.especie_id ? especies.get(c.especie_id) : null) ?? (o.especie?.id === c.especie_id ? o.especie : null) ?? null;
        return {
          cientifico: c.nombre_cientifico ?? especie?.nombre_cientifico ?? '',
          comun: c.nombre_comun ?? especie?.nombre_comun ?? null,
          confianza: c.confianza,
          especie,
          grupo: especie?.grupo ?? c.grupo ?? null,
        };
      })
      .filter((c) => !!c.cientifico);
    // Si la IA no dio candidatos pero sí una especie probable, se muestra esa.
    if (!lista.length && o.especie) {
      lista.push({ cientifico: o.especie.nombre_cientifico, comun: o.especie.nombre_comun, confianza: o.ia_confianza ?? 0, especie: o.especie,
        grupo: o.especie.grupo });
    }
    return lista;
  });

  constructor() {
    const reloj = setInterval(() => this.consejo.set(CONSEJOS[(CONSEJOS.indexOf(this.consejo()) + 1) % CONSEJOS.length]), 4500);
    inject(DestroyRef).onDestroy(() => clearInterval(reloj));
    // Foto de Wikipedia para las especies parecidas que todavía no están en el catálogo.
    effect(() => {
      if (this.vista() !== 'revisar') return;
      for (const c of this.candidatos()) {
        if (c.especie?.imagen_url || c.cientifico in this.fotosWiki()) continue;
        this.fotosWiki.update((f) => ({ ...f, [c.cientifico]: null }));
        void this.wikipedia.foto(c.cientifico).then((url) => this.fotosWiki.update((f) => ({ ...f, [c.cientifico]: url })));
      }
    });
  }

  fotoCandidato(c: CandidatoVista): string | null {
    return c.especie?.imagen_url ?? this.fotosWiki()[c.cientifico] ?? null;
  }

  estiloCandidato(c: CandidatoVista): Record<string, string> {
    return estiloGrupo(c.grupo ? { reino: c.especie?.reino ?? reinoDeGrupo(c.grupo), grupo: c.grupo } : null);
  }

  iconoCandidato(c: CandidatoVista): string {
    if (c.especie) return iconoEspecie(c.especie);
    return c.grupo ? iconoEspecie({ reino: reinoDeGrupo(c.grupo), grupo: c.grupo }) : 'leaf-outline';
  }

  confirmar(c: CandidatoVista): void {
    this.elegido.set(c.cientifico);
    this.elegir.emit(c.cientifico);
  }
}
