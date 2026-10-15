import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { MarcaComponent } from '../shared/marca.component';
import { ESTILOS_ACCESO } from './auth.styles';

/** Elegir contraseña: al recuperar la cuenta o cuando un invitado confirma su correo al crear su cuenta (?alta=1). */
@Component({
  selector: 'app-nueva-contrasena',
  imports: [FormsModule, IonContent, IonIcon, IonSpinner, MarcaComponent, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="arriba"><span></span><app-marca [tamano]="38" /></div>
        <h1>{{ alta ? '¡Correo confirmado!' : 'Nueva contraseña' }}</h1>
        <p>{{ alta ? 'Elige una contraseña para entrar a tu cuenta desde cualquier dispositivo.' : 'Escribe tu nueva contraseña.' }}</p>
      </header>
      @if (!sb.session()) {
        <div class="tarjeta-acceso">
          <p class="error-formulario">El enlace venció o ya se usó. Pide uno nuevo.</p>
          <a class="boton" routerLink="/recuperar">Pedir un enlace nuevo</a>
        </div>
      } @else {
        <form (ngSubmit)="guardar()">
          <label class="campo clave">Contraseña (mínimo 6 caracteres)
            <input [type]="verClave() ? 'text' : 'password'" name="password" autocomplete="new-password" required minlength="6" [(ngModel)]="password" />
            <button class="ver" type="button" [attr.aria-label]="verClave() ? 'Ocultar contraseña' : 'Mostrar contraseña'" (click)="verClave.set(!verClave())">
              <ion-icon [name]="verClave() ? 'eye-off-outline' : 'eye-outline'" />
            </button>
          </label>
          @if (error()) { <p class="error-formulario" role="alert">{{ error() }}</p> }
          <button class="boton" type="submit" [disabled]="cargando()">
            @if (cargando()) { <ion-spinner name="crescent" /> } Guardar contraseña
          </button>
        </form>
      }
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NuevaContrasenaPage {
  readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  readonly alta = inject(ActivatedRoute).snapshot.queryParamMap.has('alta');
  password = '';
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly verClave = signal(false);

  async guardar(): Promise<void> {
    if (this.password.length < 6) {
      this.error.set('La contraseña debe tener al menos 6 caracteres.');
      return;
    }
    this.cargando.set(true);
    try {
      await this.sb.cambiarContrasena(this.password);
      await this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
