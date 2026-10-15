import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AlertController, IonContent, IonIcon, IonRefresher, IonRefresherContent, NavController, ToastController, ViewWillEnter } from '@ionic/angular';
import { AdminService, ObservacionRevision } from '../core/admin.service';
import { CatalogoService } from '../core/catalogo.service';
import { fechaCorta } from '../core/fechas';
import { FotosService } from '../core/fotos.service';
import { iconoEspecie, nombreGrupo, porcentaje } from '../core/grupos';
import { Especie, EspecieResumen } from '../core/modelos';
import { FotoComponent } from '../shared/foto.component';

type Pestana = 'observaciones' | 'especies';

/** Panel de revisión para administradores: confirmar especies y revisar las fichas que escribió la IA. */
@Component({
  selector: 'app-revision',
  imports: [FormsModule, FotoComponent, IonContent, IonIcon, IonRefresher, IonRefresherContent, RouterLink],
  templateUrl: './revision.page.html',
  styleUrl: './revision.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RevisionPage implements ViewWillEnter {
  private readonly admin = inject(AdminService);
  private readonly catalogo = inject(CatalogoService);
  private readonly fotos = inject(FotosService);
  private readonly nav = inject(NavController);
  private readonly alert = inject(AlertController);
  private readonly toast = inject(ToastController);

  readonly pestana = signal<Pestana>('observaciones');
  readonly observaciones = signal<ObservacionRevision[] | null>(null);
  readonly especies = signal<Especie[] | null>(null);
  readonly urls = signal<Record<string, string>>({});
  readonly buscando = signal<string | null>(null);
  readonly resultados = signal<EspecieResumen[]>([]);
  readonly editando = signal<Especie | null>(null);
  textoBusqueda = '';

  readonly fechaCorta = fechaCorta;
  readonly porcentaje = porcentaje;
  readonly nombreGrupo = nombreGrupo;
  readonly iconoEspecie = iconoEspecie;

  ionViewWillEnter(): void {
    void this.cargar();
  }

  volver(): void {
    this.nav.back();
  }

  async cargar(evento?: CustomEvent): Promise<void> {
    try {
      const [obs, esp] = await Promise.all([this.admin.porRevisar(), this.admin.especiesSinVerificar()]);
      this.observaciones.set(obs);
      this.especies.set(esp);
      this.urls.set(await this.fotos.urlsFirmadas(obs.map((o) => o.ruta_foto)));
    } catch (e) {
      await this.avisar((e as Error).message);
      if (this.observaciones() === null) this.observaciones.set([]);
      if (this.especies() === null) this.especies.set([]);
    } finally {
      (evento?.target as HTMLIonRefresherElement | undefined)?.complete();
    }
  }

  async confirmar(o: ObservacionRevision, especieId: number | null): Promise<void> {
    if (!especieId) return;
    await this.guardar(o, especieId, 'corregida', 'Especie confirmada.');
  }

  async noIdentificable(o: ObservacionRevision): Promise<void> {
    await this.guardar(o, null, 'no_identificada', 'Marcada como no identificable.');
  }

  abrirBusqueda(o: ObservacionRevision): void {
    this.buscando.set(this.buscando() === o.id ? null : o.id);
    this.textoBusqueda = '';
    this.resultados.set([]);
  }

  async buscar(): Promise<void> {
    if (this.textoBusqueda.trim().length < 2) return;
    const r = await this.catalogo.buscar({ texto: this.textoBusqueda }, 0);
    this.resultados.set(r.especies.slice(0, 8));
  }

  editar(e: Especie): void {
    this.editando.set({ ...e });
  }

  async guardarEspecie(verificar: boolean): Promise<void> {
    const e = this.editando();
    if (!e) return;
    try {
      await this.admin.guardarEspecie(e.id, {
        nombre_comun: e.nombre_comun.trim(), descripcion: e.descripcion, habitat: e.habitat, alimentacion: e.alimentacion,
        tamano: e.tamano, familia: e.familia, ...(verificar ? { verificada: true } : {}),
      });
      this.editando.set(null);
      await this.avisar(verificar ? 'Ficha verificada.' : 'Cambios guardados.');
      await this.cargar();
    } catch (err) {
      await this.avisar((err as Error).message);
    }
  }

  async borrarEspecie(e: Especie): Promise<void> {
    const a = await this.alert.create({
      header: `¿Borrar «${e.nombre_comun}»?`,
      message: 'Las observaciones que la usaban quedarán sin especie (en revisión). Úsalo solo para especies erróneas o duplicadas.',
      buttons: [
        { text: 'Cancelar', role: 'cancel' },
        {
          text: 'Borrar', role: 'destructive',
          handler: async () => {
            try {
              await this.admin.borrarEspecie(e.id);
              await this.cargar();
            } catch (err) {
              await this.avisar((err as Error).message);
            }
          },
        },
      ],
    });
    await a.present();
  }

  private async guardar(o: ObservacionRevision, especieId: number | null, estado: 'corregida' | 'no_identificada', ok: string): Promise<void> {
    try {
      await this.admin.corregir(o.id, especieId, estado);
      this.observaciones.update((l) => (l ?? []).filter((x) => x.id !== o.id));
      this.buscando.set(null);
      await this.avisar(ok);
    } catch (e) {
      await this.avisar((e as Error).message);
    }
  }

  private async avisar(mensaje: string): Promise<void> {
    await (await this.toast.create({ message: mensaje, duration: 2500, color: 'dark' })).present();
  }
}
