import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Logotipo de la app: una lupa con una hoja (mismo dibujo que public/icono.svg). */
@Component({
  selector: 'app-marca',
  template: `
    <svg viewBox="0 0 512 512" [attr.width]="tamano()" [attr.height]="tamano()" role="img" aria-label="Fauna y Flora">
      <rect width="512" height="512" rx="116" fill="#1f6b4f" />
      <circle cx="226" cy="224" r="118" fill="#12452f" stroke="#f5f3ec" stroke-width="34" />
      <path d="M310 312l84 84" stroke="#e39b2d" stroke-width="46" stroke-linecap="round" />
      <path d="M226 142c-62 26-84 92-58 158 70-6 112-66 58-158z" fill="#e39b2d" />
      <path d="M168 300c18-44 38-82 58-118" stroke="#12452f" stroke-width="12" stroke-linecap="round" fill="none" />
    </svg>
    @if (conNombre()) { <span>Fauna <em>y</em> Flora</span> }
  `,
  styles: `
    :host { display: inline-flex; align-items: center; gap: 10px; }
    svg { display: block; filter: drop-shadow(0 6px 14px rgba(18, 69, 47, .25)); }
    span { font-family: var(--fuente-titulo); font-weight: 700; font-size: 21px; letter-spacing: -0.02em; color: inherit; }
    em { font-style: italic; font-weight: 450; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MarcaComponent {
  readonly tamano = input(40);
  readonly conNombre = input(false);
}
