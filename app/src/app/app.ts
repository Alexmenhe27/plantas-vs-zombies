import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';
import { IonApp, IonRouterOutlet } from '@ionic/angular';
import { CupoService } from './core/cupo.service';
import { PendientesService } from './core/pendientes.service';
import { SupabaseService } from './core/supabase.service';
import { TemaService } from './core/tema.service';
import { registrarIconos } from './shared/iconos';

@Component({
  selector: 'app-root',
  imports: [IonApp, IonRouterOutlet],
  template: `<ion-app><ion-router-outlet /></ion-app>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  private readonly sb = inject(SupabaseService);
  private readonly pendientes = inject(PendientesService);
  private readonly cupo = inject(CupoService);

  constructor() {
    registrarIconos();
    inject(TemaService); // aplica el modo claro u oscuro desde el inicio
    // Al cambiar de sesión: se actualiza el cupo y se identifican las fotos que quedaron en espera sin conexión.
    effect(() => {
      const usuario = this.sb.userId();
      if (!this.sb.listo()) return;
      if (!usuario) {
        this.cupo.limpiar();
        return;
      }
      // Primero el cupo: la cola necesita saber si ya hay identificaciones disponibles.
      void this.cupo
        .actualizar()
        .then(() => this.pendientes.cargar())
        .then(() => this.pendientes.procesar());
    });
  }
}
