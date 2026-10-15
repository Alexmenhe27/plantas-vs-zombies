import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner, NavController } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { MarcaComponent } from '../shared/marca.component';
import { ESTILOS_ACCESO } from './auth.styles';

@Component({
  selector: 'app-registro',
  imports: [FormsModule, IonContent, IonIcon, IonSpinner, MarcaComponent, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="arriba">
          <button class="volver" type="button" aria-label="Volver" (click)="volver()"><ion-icon name="arrow-back" /></button>
          <app-marca [tamano]="38" />
        </div>
        <h1>Crea tu cuenta</h1>
        <p>Es gratis. Guarda tu colección y ten más identificaciones al día.</p>
      </header>
      @if (confirmar()) {
        <div class="tarjeta-acceso">
          <p class="ok-formulario">Te enviamos un correo a <strong>{{ email }}</strong>. Abre el enlace para confirmar tu cuenta y luego inicia sesión.</p>
          <a class="boton" routerLink="/entrar">Ir a iniciar sesión</a>
        </div>
      } @else {
        <form (ngSubmit)="registrar()">
          <label class="campo">Nombre de usuario
            <input name="username" autocomplete="username" required maxlength="30" [(ngModel)]="username" />
            <small>Es el que verán los demás en tus avistamientos públicos.</small>
          </label>
          <label class="campo">Correo electrónico
            <input type="email" name="email" autocomplete="email" inputmode="email" required [(ngModel)]="email" />
          </label>
          <label class="campo clave">Contraseña (mínimo 6 caracteres)
            <input [type]="verClave() ? 'text' : 'password'" name="password" autocomplete="new-password" required minlength="6" [(ngModel)]="password" />
            <button class="ver" type="button" [attr.aria-label]="verClave() ? 'Ocultar contraseña' : 'Mostrar contraseña'" (click)="verClave.set(!verClave())">
              <ion-icon [name]="verClave() ? 'eye-off-outline' : 'eye-outline'" />
            </button>
          </label>
          @if (error()) { <p class="error-formulario" role="alert">{{ error() }}</p> }
          <button class="boton" type="submit" [disabled]="cargando()">
            @if (cargando()) { <ion-spinner name="crescent" /> } Crear cuenta
          </button>
        </form>
      }
      <div class="enlaces"><span>¿Ya tienes cuenta? <a routerLink="/entrar">Inicia sesión</a></span></div>
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RegistroPage {
  private readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  private readonly nav = inject(NavController);
  username = '';
  email = '';
  password = '';
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly confirmar = signal(false);
  readonly verClave = signal(false);

  volver(): void {
    this.nav.navigateBack('/bienvenida');
  }

  async registrar(): Promise<void> {
    const username = this.username.trim();
    if (!/^[A-Za-z0-9_.]{3,30}$/.test(username)) {
      this.error.set('El nombre de usuario debe tener de 3 a 30 letras, números, punto o guion bajo.');
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.email.trim())) {
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
      else await this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
