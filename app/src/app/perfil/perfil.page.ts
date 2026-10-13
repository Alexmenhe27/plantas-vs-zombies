import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { IonContent, IonIcon, NavController, ToastController, ViewWillEnter } from '@ionic/angular';
import { environment } from '../../environments/environment';
import { ObservacionesService } from '../core/observaciones.service';
import { SupabaseService } from '../core/supabase.service';

@Component({
  selector: 'app-perfil',
  imports: [IonContent, IonIcon, FormsModule],
  templateUrl: './perfil.page.html',
  styleUrl: './perfil.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PerfilPage implements ViewWillEnter {
  readonly sb = inject(SupabaseService);
  private readonly obs = inject(ObservacionesService);
  private readonly nav = inject(NavController);
  private readonly toast = inject(ToastController);

  readonly limite = environment.limiteDiario;
  readonly restantes = signal<number | null>(null);
  readonly email = computed(() => this.sb.session()?.user.email ?? '');
  readonly editando = signal(false);
  username = '';

  async ionViewWillEnter(): Promise<void> {
    this.restantes.set(await this.obs.restantes());
  }

  editar(): void {
    this.username = this.sb.perfil()?.nombre_usuario ?? '';
    this.editando.set(true);
  }

  async guardar(): Promise<void> {
    const u = this.username.trim();
    let mensaje = 'Nombre guardado.';
    if (!/^[A-Za-z0-9_.]{3,30}$/.test(u)) {
      mensaje = 'Usa de 3 a 30 letras, números, punto o guion bajo.';
    } else {
      try {
        await this.sb.actualizarUsername(u);
        this.editando.set(false);
      } catch (e) {
        mensaje = (e as Error).message;
      }
    }
    await (await this.toast.create({ message: mensaje, duration: 2500, color: 'dark' })).present();
  }

  async salir(): Promise<void> {
    await this.sb.cerrarSesion();
    this.nav.navigateRoot('/entrar');
  }
}
