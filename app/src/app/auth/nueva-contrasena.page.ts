import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { ESTILOS_ACCESO } from './auth.styles';

/** Se abre desde el enlace del correo de recuperación (Supabase deja una sesión temporal). */
@Component({
  selector: 'app-nueva-contrasena',
  imports: [IonContent, IonIcon, FormsModule, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="marca"><ion-icon name="leaf-outline" />Plantas vs Zombies</div>
        <h1>Nueva contraseña</h1>
        <p>Escribe la contraseña que usarás a partir de ahora.</p>
      </header>
      @if (sb.session()) {
        <form (ngSubmit)="guardar()">
          <label>Nueva contraseña (mínimo 6 caracteres)
            <input type="password" name="password" autocomplete="new-password" required minlength="6" [(ngModel)]="password" />
          </label>
          @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
          <button class="boton" type="submit" [disabled]="cargando()">Guardar contraseña</button>
        </form>
      } @else {
        <form><p class="error">El enlace no es válido o ya venció. Pide uno nuevo.</p><a class="boton" routerLink="/recuperar">Pedir otro enlace</a></form>
      }
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NuevaContrasenaPage {
  readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  password = '';
  readonly cargando = signal(false);
  readonly error = signal('');

  async guardar(): Promise<void> {
    if (this.password.length < 6) {
      this.error.set('La contraseña debe tener al menos 6 caracteres.');
      return;
    }
    this.cargando.set(true);
    try {
      await this.sb.cambiarContrasena(this.password);
      await this.router.navigateByUrl('/app/identificar', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
