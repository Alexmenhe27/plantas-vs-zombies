import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner, NavController } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { MarcaComponent } from '../shared/marca.component';
import { ESTILOS_ACCESO } from './auth.styles';

@Component({
  selector: 'app-login',
  imports: [FormsModule, IonContent, IonIcon, IonSpinner, MarcaComponent, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="arriba">
          <button class="volver" type="button" aria-label="Volver" (click)="volver()"><ion-icon name="arrow-back" /></button>
          <app-marca [tamano]="38" />
        </div>
        <h1>Qué gusto verte</h1>
        <p>Inicia sesión para seguir con tu colección.</p>
      </header>
      <form (ngSubmit)="entrar()">
        <label class="campo">Correo electrónico
          <input type="email" name="email" autocomplete="email" inputmode="email" required [(ngModel)]="email" />
        </label>
        <label class="campo clave">Contraseña
          <input [type]="verClave() ? 'text' : 'password'" name="password" autocomplete="current-password" required [(ngModel)]="password" />
          <button class="ver" type="button" [attr.aria-label]="verClave() ? 'Ocultar contraseña' : 'Mostrar contraseña'" (click)="verClave.set(!verClave())">
            <ion-icon [name]="verClave() ? 'eye-off-outline' : 'eye-outline'" />
          </button>
        </label>
        @if (error()) { <p class="error-formulario" role="alert">{{ error() }}</p> }
        <button class="boton" type="submit" [disabled]="cargando()">
          @if (cargando()) { <ion-spinner name="crescent" /> } Iniciar sesión
        </button>
        <a class="boton fantasma" routerLink="/recuperar">¿Olvidaste tu contraseña?</a>
      </form>
      <div class="enlaces">
        <span>¿No tienes cuenta? <a routerLink="/registro">Regístrate gratis</a></span>
      </div>
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPage {
  private readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  private readonly nav = inject(NavController);
  email = '';
  password = '';
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly verClave = signal(false);

  volver(): void {
    this.nav.navigateBack('/bienvenida');
  }

  async entrar(): Promise<void> {
    if (!this.email || !this.password) {
      this.error.set('Escribe tu correo y tu contraseña.');
      return;
    }
    this.cargando.set(true);
    this.error.set('');
    try {
      await this.sb.iniciarSesion(this.email.trim(), this.password);
      await this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
