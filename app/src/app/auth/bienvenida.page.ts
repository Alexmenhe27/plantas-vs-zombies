import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner } from '@ionic/angular';
import { SupabaseService } from '../core/supabase.service';
import { MarcaComponent } from '../shared/marca.component';

/** Primera pantalla: se puede empezar sin cuenta (modo invitado) en un toque. */
@Component({
  selector: 'app-bienvenida',
  imports: [IonContent, IonIcon, IonSpinner, MarcaComponent, RouterLink],
  template: `
    <ion-content>
      <div class="pantalla">
        <div class="paisaje" aria-hidden="true">
          <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMax slice">
            <path d="M0 210 Q80 150 160 190 T320 170 T400 180 V300 H0Z" fill="#2c8a63" opacity=".55" />
            <path d="M0 240 Q100 190 200 230 T400 215 V300 H0Z" fill="#1f6b4f" />
            <path d="M60 240c0-30 18-52 40-60-4 26-18 46-40 60z" fill="#5ec79b" />
            <path d="M330 232c-4-34 10-58 34-70 2 30-12 54-34 70z" fill="#5ec79b" />
            <path d="M0 270 Q120 240 220 262 T400 255 V300 H0Z" fill="#12452f" />
          </svg>
        </div>
        <div class="contenido">
          <app-marca [tamano]="54" [conNombre]="true" />
          <h1>Descubre qué vive a tu alrededor</h1>
          <p class="sub">Toma una foto de un animal o una planta y en segundos te decimos qué especie es.</p>
          <ul>
            <li><ion-icon name="flash-outline" /><span>El nombre aparece en segundos</span></li>
            <li><ion-icon name="albums-outline" /><span>Arma tu colección de especies</span></li>
            <li><ion-icon name="lock-closed-outline" /><span>Tus fotos y tu ubicación son privadas</span></li>
          </ul>
          @if (error()) { <p class="error-formulario" role="alert">{{ error() }}</p> }
          <div class="botones">
            <button class="boton acento grande" type="button" (click)="empezar()" [disabled]="cargando()">
              @if (cargando()) { <ion-spinner name="crescent" /> } @else { <ion-icon name="arrow-forward" /> }
              Empezar sin cuenta
            </button>
            <a class="boton vidrio" routerLink="/entrar">Ya tengo cuenta</a>
            <a class="crear" routerLink="/registro">Crear una cuenta gratis</a>
          </div>
        </div>
      </div>
    </ion-content>
  `,
  styles: `
    .pantalla {
      min-height: 100%; position: relative; overflow: hidden; color: #fff; display: flex; flex-direction: column;
      background: radial-gradient(120% 70% at 0% 0%, rgba(94, 199, 155, .25), transparent 60%), linear-gradient(170deg, #1f6b4f 0%, #12452f 70%);
    }
    .paisaje { position: absolute; left: 0; right: 0; bottom: 0; height: 38%; pointer-events: none; opacity: .5; }
    .paisaje svg { width: 100%; height: 100%; display: block; }
    .contenido { position: relative; flex: 1; display: flex; flex-direction: column; gap: 18px; padding: calc(36px + env(safe-area-inset-top)) 24px calc(24px + env(safe-area-inset-bottom)); }
    app-marca { color: #fff; }
    h1 { margin: 16px 0 0; font-size: 36px; line-height: 1.08; color: #fff; }
    .sub { margin: 0; font-size: 17px; line-height: 1.5; color: rgba(255, 255, 255, .85); }
    ul { list-style: none; margin: 4px 0 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
    li { display: flex; align-items: center; gap: 12px; font-size: 15.5px; font-weight: 650; }
    li ion-icon { width: 38px; height: 38px; padding: 8px; border-radius: 12px; background: rgba(255, 255, 255, .12); color: #f1b549; flex: none; box-sizing: border-box; }
    .botones { margin-top: auto; display: flex; flex-direction: column; gap: 10px; padding-top: 18px; }
    .grande { min-height: 58px; font-size: 17px; }
    .grande ion-spinner { width: 20px; height: 20px; color: inherit; }
    .vidrio { background: rgba(255, 255, 255, .14); color: #fff; border: 1.5px solid rgba(255, 255, 255, .3); backdrop-filter: blur(6px); }
    .crear { align-self: center; color: #fff; font-weight: 750; font-size: 15px; padding: 8px; }
    .legal { align-self: center; color: rgba(255, 255, 255, .7); font-size: 12.5px; }
    .error-formulario { background: #fbe2dc; color: #972a19; }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BienvenidaPage {
  private readonly sb = inject(SupabaseService);
  private readonly router = inject(Router);
  readonly cargando = signal(false);
  readonly error = signal('');

  async empezar(): Promise<void> {
    this.cargando.set(true);
    this.error.set('');
    try {
      if (!this.sb.session()) await this.sb.entrarComoInvitado();
      await this.router.navigateByUrl('/app/inicio', { replaceUrl: true });
    } catch (e) {
      this.error.set((e as Error).message);
    } finally {
      this.cargando.set(false);
    }
  }
}
