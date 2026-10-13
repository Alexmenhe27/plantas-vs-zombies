import { ChangeDetectionStrategy, Component } from '@angular/core';
import { IonIcon, IonLabel, IonTabBar, IonTabButton, IonTabs } from '@ionic/angular';

@Component({
  selector: 'app-tabs',
  imports: [IonTabs, IonTabBar, IonTabButton, IonIcon, IonLabel],
  template: `
    <ion-tabs>
      <ion-tab-bar slot="bottom">
        <ion-tab-button tab="identificar"><ion-icon name="tab-identificar" /><ion-label>Identificar</ion-label></ion-tab-button>
        <ion-tab-button tab="explorar"><ion-icon name="tab-explorar" /><ion-label>Explorar</ion-label></ion-tab-button>
        <ion-tab-button tab="historial"><ion-icon name="tab-historial" /><ion-label>Historial</ion-label></ion-tab-button>
        <ion-tab-button tab="perfil"><ion-icon name="tab-perfil" /><ion-label>Perfil</ion-label></ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>
  `,
  styles: `
    ion-tab-bar { border-top: 1px solid var(--app-borde); height: 72px; padding-bottom: env(safe-area-inset-bottom); }
    ion-tab-button { font-weight: 600; --ripple-color: transparent; }
    ion-tab-button ion-icon { width: 56px; height: 30px; padding: 4px 0; border-radius: 15px; font-size: 22px; }
    ion-tab-button.tab-selected { font-weight: 800; }
    ion-tab-button.tab-selected ion-icon { background: var(--app-verde-claro); }
    ion-label { font-size: 12px; margin-top: 4px; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TabsPage {}
