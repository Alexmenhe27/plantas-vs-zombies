import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner, IonToggle, ViewWillEnter } from '@ionic/angular';
import { CatalogoService } from '../core/catalogo.service';
import { GRUPOS, etiquetaConservacion, iconoEspecie, nombreGrupo } from '../core/grupos';
import { Especie } from '../core/modelos';
import { FotoComponent } from '../shared/foto.component';

function normalizar(t: string): string {
  return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

@Component({
  selector: 'app-catalogo',
  imports: [FotoComponent, IonContent, IonIcon, IonSpinner, IonToggle, RouterLink],
  templateUrl: './catalogo.page.html',
  styleUrl: './catalogo.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogoPage implements ViewWillEnter {
  readonly iconoEspecie = iconoEspecie;
  private readonly catalogo = inject(CatalogoService);
  private readonly route = inject(ActivatedRoute);

  readonly grupos = GRUPOS;
  readonly grupo = signal('todos');
  readonly soloProtegidas = signal(false);
  readonly busqueda = signal('');
  readonly cargando = signal(true);
  readonly error = signal(false);

  readonly filtradas = computed(() => {
    const g = GRUPOS.find((x) => x.id === this.grupo());
    const q = normalizar(this.busqueda().trim());
    return this.catalogo.especies().filter(
      (e) =>
        (!g || g.incluye(e)) &&
        (!this.soloProtegidas() || e.protegida) &&
        (!q || normalizar(e.nombre_comun).includes(q) || normalizar(e.nombre_cientifico).includes(q)),
    );
  });

  readonly etiqueta = etiquetaConservacion;
  readonly nombreGrupo = nombreGrupo;

  async ionViewWillEnter(): Promise<void> {
    const g = this.route.snapshot.queryParamMap.get('grupo');
    if (g) this.grupo.set(g);
    try {
      await this.catalogo.cargar();
      this.error.set(false);
    } catch {
      this.error.set(true);
    } finally {
      this.cargando.set(false);
    }
  }

  clase(e: Especie): string {
    if (e.categoria_nom059 === 'P') return 'chip rojo';
    if (e.categoria_nom059) return 'chip ambar';
    return 'chip gris';
  }

  buscar(evento: Event): void {
    this.busqueda.set((evento.target as HTMLInputElement).value);
  }
}
