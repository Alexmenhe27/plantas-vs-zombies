import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AlertController, IonContent, IonIcon, IonSpinner, IonToggle, NavController, ToastController, ViewWillEnter } from '@ionic/angular';
import { CupoService } from '../core/cupo.service';
import { SupabaseService } from '../core/supabase.service';
import { UbicacionService } from '../core/ubicacion.service';
import { MarcaComponent } from '../shared/marca.component';

const USUARIO_VALIDO = /^[A-Za-z0-9_.]{3,30}$/;

@Component({
  selector: 'app-perfil',
  imports: [FormsModule, IonContent, IonIcon, IonSpinner, IonToggle, MarcaComponent, RouterLink],
  templateUrl: './perfil.page.html',
  styleUrl: './perfil.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PerfilPage implements ViewWillEnter {
  readonly sb = inject(SupabaseService);
  readonly ubicacion = inject(UbicacionService);
  private readonly cupoService = inject(CupoService);
  private readonly nav = inject(NavController);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastController);
  private readonly alert = inject(AlertController);

  readonly cupo = this.cupoService.cupo;
  readonly email = computed(() => this.sb.session()?.user.email ?? '');
  readonly editando = signal(false);
  readonly guardando = signal(false);
  readonly creando = signal(false);
  readonly errorCrear = signal('');
  readonly enviado = signal(false);
  username = '';
  nuevoCorreo = '';
  nuevoUsuario = '';

  ionViewWillEnter(): void {
    void this.cupoService.actualizar();
    if (this.route.snapshot.queryParamMap.get('crear') && this.sb.esInvitado()) {
      setTimeout(() => document.getElementById('crear-cuenta')?.scrollIntoView({ behavior: 'smooth' }), 300);
    }
  }

  editar(): void {
    this.username = this.sb.perfil()?.nombre_usuario ?? '';
    this.editando.set(true);
  }

  async guardar(): Promise<void> {
    const u = this.username.trim();
    if (!USUARIO_VALIDO.test(u)) {
      await this.avisar('Usa de 3 a 30 letras, números, punto o guion bajo.');
      return;
    }
    this.guardando.set(true);
    try {
      await this.sb.actualizarUsername(u);
      this.editando.set(false);
      await this.avisar('Nombre guardado.');
    } catch (e) {
      await this.avisar((e as Error).message);
    } finally {
      this.guardando.set(false);
    }
  }

  /** Un invitado crea su cuenta sin perder su colección. */
  async crearCuenta(): Promise<void> {
    const correo = this.nuevoCorreo.trim();
    const usuario = this.nuevoUsuario.trim();
    this.errorCrear.set('');
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correo)) {
      this.errorCrear.set('Escribe un correo válido.');
      return;
    }
    if (!USUARIO_VALIDO.test(usuario)) {
      this.errorCrear.set('El nombre de usuario debe tener de 3 a 30 letras, números, punto o guion bajo.');
      return;
    }
    this.creando.set(true);
    try {
      await this.sb.crearCuentaDesdeInvitado(correo, usuario);
      this.enviado.set(true);
    } catch (e) {
      this.errorCrear.set((e as Error).message);
    } finally {
      this.creando.set(false);
    }
  }

  async cambiarPublicar(evento: CustomEvent): Promise<void> {
    try {
      await this.sb.cambiarPublicarPorDefecto(!!evento.detail.checked);
    } catch (e) {
      await this.avisar((e as Error).message);
    }
  }

  cambiarUbicacion(evento: CustomEvent): void {
    this.ubicacion.cambiarPermitida(!!evento.detail.checked);
  }

  async salir(): Promise<void> {
    if (this.sb.esInvitado()) {
      const a = await this.alert.create({
        header: '¿Salir sin cuenta?',
        message: 'Estás usando la app sin cuenta: si sales, no podrás volver a ver tu colección. Mejor crea tu cuenta gratis.',
        buttons: [{ text: 'Cancelar', role: 'cancel' }, { text: 'Salir de todos modos', role: 'destructive', handler: () => void this.cerrarSesion() }],
      });
      await a.present();
      return;
    }
    await this.cerrarSesion();
  }

  private async cerrarSesion(): Promise<void> {
    await this.sb.cerrarSesion();
    this.cupoService.limpiar();
    this.nav.navigateRoot('/bienvenida');
  }

  private async avisar(mensaje: string): Promise<void> {
    await (await this.toast.create({ message: mensaje, duration: 2800, color: 'dark' })).present();
  }
}
