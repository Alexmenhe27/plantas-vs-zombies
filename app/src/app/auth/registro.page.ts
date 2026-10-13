import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { ESTILOS_ACCESO } from './auth.styles';

@Component({
  selector: 'app-registro',
  imports: [IonContent, IonIcon, FormsModule, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="marca"><ion-icon name="leaf-outline" /></div>
        <h1>Crea tu cuenta</h1>
        <p>Identifica hasta 10 especies al día y guarda tu historial.</p>
      </header>
      @if (confirmar()) {
        <form>
          <p class="ok" role="status">Te enviamos un correo a {{ email }}. Abre el enlace para confirmar tu cuenta y después inicia sesión.</p>
          <a class="boton" routerLink="/entrar">Ir a iniciar sesión</a>
        </form>
      } @else {
        <form (ngSubmit)="registrar()">
          <label>Nombre de usuario
            <input name="username" autocomplete="username" required minlength="3" maxlength="30" [(ngModel)]="username" />
          </label>
          <label>Correo electrónico
            <input type="email" name="email" autocomplete="email" required [(ngModel)]="email" />
          </label>
          <label>Contraseña (mínimo 6 caracteres)
            <input type="password" name="password" autocomplete="new-password" required minlength="6" [(ngModel)]="password" />
          </label>
          @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
          <button class="boton" type="submit" [disabled]="cargando()">{{ cargando() ? 'Creando cuenta…' : 'Crear cuenta' }}</button>
        </form>
      }
      <div class="enlaces"><span class="texto-suave">¿Ya tienes cuenta? <a routerLink="/entrar">Inicia sesión</a></span></div>
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegistroPage {
  private readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  username = '';
  email = '';
  password = '';
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly confirmar = signal(false);

  async registrar(): Promise<void> {
    const username = this.username.trim();
    if (!/^[A-Za-z0-9_.]{3,30}$/.test(username)) {
      this.error.set('El nombre de usuario debe tener de 3 a 30 letras, números, punto o guion bajo.');
      return;
    }
    if (!this.email.includes('@')) {
      this.error.set('Escribe un correo válido.');
      return;
    }
    if (this.password.length < 6) {
      this.error.set('La contraseña debe tener al menos 6 caracteres.');
      return;
    }
    this.cargando.set(true);
    this.error.set('');
    try {
      const debeConfirmar = await this.sb.registrarse(this.email.trim(), this.password, username);
      if (debeConfirmar) this.confirmar.set(true);
      else await this.router.navigateByUrl('/app/identificar', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
