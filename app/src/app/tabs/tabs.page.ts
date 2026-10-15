import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { IonIcon, IonLabel, IonSpinner, IonTabBar, IonTabButton, IonTabs } from '@ionic/angular';
import { IdentificacionService } from '../core/identificacion.service';
import { PendientesService } from '../core/pendientes.service';
import { vibrarToque } from '../core/hapticos';

/** Barra inferior: 4 pestañas y, al centro, la cámara (identificar está a un toque desde cualquier pantalla). */
@Component({
  selector: 'app-tabs',
  imports: [IonTabs, IonTabBar, IonTabButton, IonIcon, IonLabel, IonSpinner],
  template: `
    <ion-tabs>
      <ion-tab-bar slot="bottom">
        <ion-tab-button tab="inicio"><ion-icon name="home-outline" /><ion-label>Inicio</ion-label></ion-tab-button>
        <ion-tab-button tab="explorar"><ion-icon name="tab-explorar" /><ion-label>Explorar</ion-label></ion-tab-button>
        <button class="camara" type="button" aria-label="Tomar foto para identificar" [disabled]="identificacion.ocupado()" (click)="camara()">
          @if (identificacion.ocupado()) { <ion-spinner name="crescent" /> } @else { <ion-icon name="tab-identificar" /> }
          @if (pendientes.lista().length) { <span class="globo" [attr.aria-label]="pendientes.lista().length + ' fotos en espera'">{{ pendientes.lista().length }}</span> }
        </button>
        <ion-tab-button tab="coleccion"><ion-icon name="tab-coleccion" /><ion-label>Colección</ion-label></ion-tab-button>
        <ion-tab-button tab="perfil"><ion-icon name="tab-perfil" /><ion-label>Perfil</ion-label></ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>
  `,
  styles: `
    ion-tab-bar {
      --background: var(--c-superficie); --border: 0; --color: var(--c-texto-3); --color-selected: var(--c-primario-texto);
      height: 74px; padding-bottom: env(safe-area-inset-bottom); box-shadow: 0 -1px 0 var(--c-borde), 0 -10px 30px rgba(0, 0, 0, .04);
      overflow: visible; contain: none;
    }
    ion-tab-button { font-weight: 650; --ripple-color: transparent; max-width: 86px; min-width: 0; --padding-start: 0; --padding-end: 0; }
    ion-tab-button ion-icon { width: 54px; height: 30px; padding: 4px 0; border-radius: 15px; font-size: 22px; transition: background .2s; }
    ion-tab-button.tab-selected { font-weight: 800; }
    ion-tab-button.tab-selected ion-icon { background: var(--c-primario-suave); }
    ion-label { font-size: 11px; margin-top: 3px; letter-spacing: 0; overflow: visible; text-overflow: clip; }
    .camara {
      position: relative; flex: none; width: 66px; height: 66px; margin: -26px 6px 0; border-radius: 50%; border: 5px solid var(--c-fondo);
      background: var(--c-primario); color: var(--c-sobre-primario); display: flex; align-items: center; justify-content: center;
      box-shadow: 0 10px 24px rgba(18, 69, 47, .35); cursor: pointer; transition: transform .15s var(--curva);
      -webkit-tap-highlight-color: transparent;
    }
    .camara:active { transform: scale(.94); }
    .camara ion-icon { font-size: 28px; }
    .camara ion-spinner { color: inherit; width: 26px; height: 26px; }
    .globo { position: absolute; top: -4px; right: -4px; min-width: 22px; height: 22px; padding: 0 6px; border-radius: 11px; background: var(--c-acento); color: #2e1b02; font-size: 12px; font-weight: 800; display: flex; align-items: center; justify-content: center; border: 2px solid var(--c-fondo); }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TabsPage {
  readonly identificacion = inject(IdentificacionService);
  readonly pendientes = inject(PendientesService);

  camara(): void {
    void vibrarToque();
    void this.identificacion.empezar('camara');
  }
}
