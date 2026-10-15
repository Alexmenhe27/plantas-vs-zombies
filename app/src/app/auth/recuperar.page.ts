import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner, NavController } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { MarcaComponent } from '../shared/marca.component';
import { ESTILOS_ACCESO } from './auth.styles';

@Component({
  selector: 'app-recuperar',
  imports: [FormsModule, IonContent, IonIcon, IonSpinner, MarcaComponent, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="arriba">
          <button class="volver" type="button" aria-label="Volver" (click)="volver()"><ion-icon name="arrow-back" /></button>
          <app-marca [tamano]="38" />
        </div>
        <h1>Recupera tu contraseña</h1>
        <p>Te enviaremos un enlace para crear una nueva.</p>
      </header>
      @if (enviado()) {
        <div class="tarjeta-acceso">
          <p class="ok-formulario">Si existe una cuenta con <strong>{{ email }}</strong>, te llegará un correo con el enlace. Revisa también tu carpeta de spam.</p>
          <a class="boton" routerLink="/entrar">Volver a iniciar sesión</a>
        </div>
      } @else {
        <form (ngSubmit)="enviar()">
          <label class="campo">Correo electrónico
            <input type="email" name="email" autocomplete="email" inputmode="email" required [(ngModel)]="email" />
          </label>
          @if (error()) { <p class="error-formulario" role="alert">{{ error() }}</p> }
          <button class="boton" type="submit" [disabled]="cargando()">
            @if (cargando()) { <ion-spinner name="crescent" /> } Enviar enlace
          </button>
        </form>
      }
      <div class="enlaces"><a routerLink="/entrar">Volver a iniciar sesión</a></div>
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RecuperarPage {
  private readonly sb = inject(SupabaseService);
  private readonly nav = inject(NavController);
  email = '';
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly enviado = signal(false);

  volver(): void {
    this.nav.back();
  }

  async enviar(): Promise<void> {
    if (!this.email.includes('@')) {
      this.error.set('Escribe un correo válido.');
      return;
    }
    this.cargando.set(true);
    this.error.set('');
    try {
      await this.sb.recuperarContrasena(this.email.trim());
      this.enviado.set(true);
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
