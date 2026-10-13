import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { IonIcon } from '@ionic/angular';

/**
 * Muestra una imagen dentro de una caja de tamaño fijo, recortada sin deformarse (object-fit: cover).
 * Mientras carga, o si no hay imagen o el enlace falla, muestra un icono en su lugar.
 * El tamaño lo decide quien lo usa (ancho/alto o aspect-ratio sobre la etiqueta <pvz-foto>).
 */
@Component({
  selector: 'pvz-foto',
  imports: [IonIcon],
  template: `
    @if (src() && !fallo()) {
      <img [src]="src()" [alt]="alt()" [class.lista]="cargada()" [attr.loading]="diferida() ? 'lazy' : null" decoding="async"
           (load)="cargadaEn.set(src())" (error)="falloEn.set(src())" />
    }
    @if (!cargada()) {
      <span class="respaldo" aria-hidden="true"><ion-icon [name]="icono()" /></span>
    }
  `,
  styles: `
    :host { display: block; position: relative; overflow: hidden; background: var(--pvz-verde-claro); flex: none; }
    img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; opacity: 0; transition: opacity .2s; }
    img.lista { opacity: 1; }
    .respaldo { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
    ion-icon { font-size: var(--pvz-foto-icono, 26px); color: var(--pvz-verde); opacity: .75; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FotoComponent {
  readonly src = input<string | null | undefined>(null);
  readonly alt = input('');
  readonly icono = input('image-outline');
  /** Las listas largas cargan las fotos solo cuando se acercan a la pantalla. */
  readonly diferida = input(true);

  readonly cargadaEn = signal<string | null | undefined>(null);
  readonly falloEn = signal<string | null | undefined>(null);
  readonly cargada = computed(() => !!this.src() && this.cargadaEn() === this.src());
  readonly fallo = computed(() => !!this.src() && this.falloEn() === this.src());
}
