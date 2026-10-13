import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { IonContent, IonIcon } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { ESTILOS_ACCESO } from './auth.styles';

@Component({
  selector: 'app-recuperar',
  imports: [IonContent, IonIcon, FormsModule, RouterLink],
  template: `
    <ion-content>
      <header class="cabecera">
        <div class="marca"><ion-icon name="leaf-outline" /></div>
        <h1>Recupera tu contraseña</h1>
        <p>Te enviaremos un enlace para crear una nueva.</p>
      </header>
      <form (ngSubmit)="enviar()">
        <label>Correo electrónico
          <input type="email" name="email" autocomplete="email" required [(ngModel)]="email" />
        </label>
        @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
        @if (enviado()) { <p class="ok" role="status">Si existe una cuenta con ese correo, te llegará un enlace en unos minutos.</p> }
        <button class="boton" type="submit" [disabled]="cargando()">Enviar enlace</button>
      </form>
      <div class="enlaces"><a routerLink="/entrar">Volver a iniciar sesión</a></div>
    </ion-content>
  `,
  styles: ESTILOS_ACCESO,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RecuperarPage {
  private readonly sb = inject(SupabaseService);
  email = '';
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly enviado = signal(false);

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
