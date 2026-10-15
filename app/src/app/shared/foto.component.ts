import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { IonIcon } from '@ionic/angular';

/**
 * Muestra una imagen dentro de una caja de tamaño fijo, recortada sin deformarse (object-fit: cover).
 * Mientras carga muestra un brillo suave; si no hay imagen o el enlace falla, el icono del grupo.
 * `respaldo`: otra dirección por si la primera falla (p. ej. la foto completa cuando no hay miniatura).
 * El tamaño lo decide quien lo usa (ancho/alto o aspect-ratio sobre la etiqueta <app-foto>).
 */
@Component({
  selector: 'app-foto',
  imports: [IonIcon],
  template: `
    @if (actual(); as url) {
      <img [src]="url" [alt]="alt()" [class.lista]="cargada()" [attr.loading]="diferida() ? 'lazy' : null" decoding="async"
           (load)="cargadaEn.set(url)" (error)="fallo(url)" />
    }
    @if (!cargada()) {
      <span class="respaldo" [class.cargando]="!!actual()" aria-hidden="true"><ion-icon [name]="icono()" /></span>
    }
  `,
  styles: `
    :host { display: block; position: relative; overflow: hidden; background: var(--grupo-suave, var(--c-primario-suave)); flex: none; }
    img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; display: block; opacity: 0; transition: opacity .3s ease; }
    img.lista { opacity: 1; }
    .respaldo { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
    .respaldo.cargando { background: linear-gradient(90deg, transparent, rgba(255,255,255,.18), transparent); background-size: 200% 100%; animation: brillo 1.3s ease-in-out infinite; }
    ion-icon { font-size: var(--app-foto-icono, 26px); color: var(--grupo, var(--c-primario)); opacity: .7; }
    @keyframes brillo { from { background-position: 200% 0; } to { background-position: -200% 0; } }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FotoComponent {
  readonly src = input<string | null | undefined>(null);
  readonly respaldo = input<string | null | undefined>(null);
  readonly alt = input('');
  readonly icono = input('image-outline');
  /** Las listas largas cargan las fotos solo cuando se acercan a la pantalla. */
  readonly diferida = input(true);

  readonly cargadaEn = signal<string | null>(null);
  private readonly fallidas = signal<ReadonlySet<string>>(new Set());
  readonly actual = computed(() => [this.src(), this.respaldo()].find((u): u is string => !!u && !this.fallidas().has(u)) ?? null);
  readonly cargada = computed(() => !!this.actual() && this.cargadaEn() === this.actual());

  fallo(url: string): void {
    this.fallidas.update((s) => new Set(s).add(url));
  }
}
