import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonIcon } from '@ionic/angular';
import { etiquetaConservacion, estiloGrupo, iconoEspecie, nombreGrupo } from '../core/grupos';
import { EspecieResumen } from '../core/modelos';
import { FotoComponent } from './foto.component';

/** Tarjeta de una especie (Explorar y Colección): foto grande, nombres y estado de conservación. */
@Component({
  selector: 'app-tarjeta-especie',
  imports: [FotoComponent, IonIcon, RouterLink],
  template: `
    @let e = especie();
    <a class="tarjeta-especie" [routerLink]="['/especie', e.id]" [style]="estilo()" [attr.aria-label]="e.nombre_comun">
      <app-foto class="foto" [src]="foto() ?? e.imagen_url" [respaldo]="respaldo() ?? e.imagen_url" [icono]="icono()" [alt]="''" />
      <span class="chip grupo arriba">{{ nombreGrupo(e.grupo) }}</span>
      @if (veces() > 1) { <span class="veces">×{{ veces() }}</span> }
      <span class="texto">
        <strong>{{ e.nombre_comun }}</strong>
        <span class="cientifico">{{ e.nombre_cientifico }}</span>
        @if (conservacion(); as c) {
          <span class="estado" [class.protegida]="!!e.categoria_nom059"><ion-icon [name]="e.categoria_nom059 ? 'shield-checkmark-outline' : 'earth-outline'" />{{ c }}</span>
        }
      </span>
    </a>
  `,
  styles: `
    .tarjeta-especie {
      position: relative; display: flex; flex-direction: column; height: 100%;
      border-radius: var(--radio-l); overflow: hidden; text-decoration: none; color: var(--c-texto);
      background: var(--c-superficie); border: 1px solid var(--c-borde); box-shadow: var(--sombra-1);
      transition: transform .2s var(--curva);
    }
    .tarjeta-especie:active { transform: scale(.98); }
    .foto { width: 100%; aspect-ratio: 1 / 1; --app-foto-icono: 38px; }
    .arriba { position: absolute; top: 10px; left: 10px; background: rgba(255, 255, 255, .9); color: var(--grupo); backdrop-filter: blur(6px); }
    .veces { position: absolute; top: 10px; right: 10px; padding: 5px 9px; border-radius: 999px; background: rgba(24, 32, 27, .78); color: #fff; font-size: 12px; font-weight: 800; }
    .texto { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px 12px; min-width: 0; }
    strong { font-size: 15px; line-height: 1.25; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .cientifico { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .estado { margin-top: 4px; display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 750; color: var(--c-texto-2); }
    .estado.protegida { color: var(--c-acento-texto); }
    .estado ion-icon { font-size: 14px; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TarjetaEspecieComponent {
  readonly especie = input.required<EspecieResumen>();
  /** Foto propia de la persona (en la colección); si no, la de referencia del catálogo. */
  readonly foto = input<string | null>(null);
  readonly respaldo = input<string | null>(null);
  readonly veces = input(0);

  readonly nombreGrupo = nombreGrupo;
  readonly estilo = computed(() => estiloGrupo(this.especie()));
  readonly icono = computed(() => iconoEspecie(this.especie()));
  readonly conservacion = computed(() => etiquetaConservacion(this.especie()));
}
