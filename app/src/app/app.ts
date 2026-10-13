import { ChangeDetectionStrategy, Component } from '@angular/core';
import { IonApp, IonRouterOutlet } from '@ionic/angular';
import { registrarIconos } from './shared/iconos';

@Component({
  selector: 'app-root',
  imports: [IonApp, IonRouterOutlet],
  template: `<ion-app><ion-router-outlet /></ion-app>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  constructor() {
    registrarIconos();
  }
}
