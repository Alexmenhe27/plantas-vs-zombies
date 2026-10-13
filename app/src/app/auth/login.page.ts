import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { ESTILOS_ACCESO } from './auth.styles';

@Component({
  selector: 'app-login',
  imports: [IonContent, IonIcon, FormsModule, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="marca"><ion-icon name="leaf-outline" /></div>
        <h1>Descubre la vida silvestre que te rodea</h1>
        <p>Inicia sesión para identificar especies y guardar tus observaciones.</p>
      </header>
      <form (ngSubmit)="entrar()">
        <label>Correo electrónico
          <input type="email" name="email" autocomplete="email" required [(ngModel)]="email" />
        </label>
        <label>Contraseña
          <input type="password" name="password" autocomplete="current-password" required [(ngModel)]="password" />
        </label>
        @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
        <button class="boton" type="submit" [disabled]="cargando()">{{ cargando() ? 'Entrando…' : 'Iniciar sesión' }}</button>
      </form>
      <div class="enlaces">
        <a routerLink="/recuperar">¿Olvidaste tu contraseña?</a>
        <span class="texto-suave">¿No tienes cuenta? <a routerLink="/registro">Regístrate</a></span>
      </div>
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPage {
  private readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  email = '';
  password = '';
  readonly cargando = signal(false);
  readonly error = signal('');

  async entrar(): Promise<void> {
    if (!this.email || !this.password) {
      this.error.set('Escribe tu correo y tu contraseña.');
      return;
    }
    this.cargando.set(true);
    this.error.set('');
    try {
      await this.sb.iniciarSesion(this.email.trim(), this.password);
      await this.router.navigateByUrl('/app/identificar', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
