import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { IonIcon } from '@ionic/angular';
import { Fase } from '../core/identificacion.service';

/** La foto grande del resultado. Mientras la IA trabaja muestra un escaneo animado y en qué paso va. */
@Component({
  selector: 'app-foto-analisis',
  imports: [IonIcon],
  template: `
    <div class="marco" [class.analizando]="trabajando()">
      @if (src(); as s) { <img [src]="s" [alt]="alt()" /> } @else { <div class="sin-foto esqueleto"></div> }
      @if (trabajando()) {
        <div class="escaneo" aria-hidden="true">
          <span class="esquina a"></span><span class="esquina b"></span><span class="esquina c"></span><span class="esquina d"></span>
          <span class="linea"></span>
        </div>
      }
      <div class="arriba"><ng-content select="[barra]" /></div>
      @if (trabajando()) {
        <span class="estado" role="status"><span class="pulso"></span>{{ textoFase() }}</span>
      } @else if (exito()) {
        <span class="estado ok"><ion-icon name="checkmark-circle" />{{ exito() }}</span>
      }
    </div>
  `,
  styles: `
    :host { display: block; }
    .marco { position: relative; overflow: hidden; border-radius: 0 0 var(--radio-xl) var(--radio-xl); background: #10170f; aspect-ratio: 4 / 4.4; max-height: 56vh; width: 100%; }
    img, .sin-foto { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .sin-foto { border-radius: 0; }
    .analizando img { filter: saturate(.9) brightness(.92); }
    .arriba { position: absolute; top: calc(12px + env(safe-area-inset-top)); left: 14px; right: 14px; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .escaneo { position: absolute; inset: 14% 12%; }
    .esquina { position: absolute; width: 34px; height: 34px; border: 3px solid rgba(255, 255, 255, .92); }
    .a { top: 0; left: 0; border-right: 0; border-bottom: 0; border-radius: 14px 0 0 0; }
    .b { top: 0; right: 0; border-left: 0; border-bottom: 0; border-radius: 0 14px 0 0; }
    .c { bottom: 0; left: 0; border-right: 0; border-top: 0; border-radius: 0 0 0 14px; }
    .d { bottom: 0; right: 0; border-left: 0; border-top: 0; border-radius: 0 0 14px 0; }
    .linea {
      position: absolute; left: 4%; right: 4%; height: 2px; top: 0;
      background: linear-gradient(90deg, transparent, #f1b549, transparent);
      box-shadow: 0 0 18px 4px rgba(241, 181, 73, .55);
      animation: barrer 2.2s ease-in-out infinite alternate;
    }
    @keyframes barrer { from { top: 2%; } to { top: 98%; } }
    .estado {
      position: absolute; left: 50%; bottom: 40px; transform: translateX(-50%);
      display: inline-flex; align-items: center; gap: 8px; white-space: nowrap;
      padding: 9px 16px; border-radius: 999px; background: rgba(14, 20, 17, .72); color: #fff;
      font-size: 14px; font-weight: 750; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    }
    .estado.ok { background: #e8f7ee; color: #12452f; animation: subir .45s var(--curva) both; }
    @keyframes subir { from { opacity: 0; transform: translate(-50%, 10px); } to { opacity: 1; transform: translate(-50%, 0); } }
    .estado ion-icon { font-size: 19px; color: #2b9767; }
    .pulso { width: 9px; height: 9px; border-radius: 50%; background: #f1b549; animation: pulso 1.1s ease-in-out infinite; }
    @keyframes pulso { 0%, 100% { opacity: .35; transform: scale(.8); } 50% { opacity: 1; transform: scale(1.15); } }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FotoAnalisisComponent {
  readonly src = input<string | null>(null);
  readonly alt = input('Tu foto');
  readonly fase = input<Fase | 'guardada'>('guardada');
  /** Texto de la etiqueta de éxito (p. ej. "¡Especie identificada!"). */
  readonly exito = input<string | null>(null);

  readonly trabajando = computed(() => this.fase() === 'subiendo' || this.fase() === 'analizando');
  readonly textoFase = computed(() => (this.fase() === 'subiendo' ? 'Enviando tu foto' : 'Analizando rasgos'));
}
