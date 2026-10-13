import { Injectable, inject, signal } from '@angular/core';
import { Especie } from './modelos';
import { SupabaseService } from './supabase.service';

/** Catálogo de especies (se lee una vez y se vuelve a leer cuando una identificación agrega especies). */
@Injectable({ providedIn: 'root' })
export class CatalogoService {
  private readonly sb = inject(SupabaseService);
  readonly especies = signal<Especie[]>([]);
  private carga: Promise<Especie[]> | null = null;

  cargar(forzar = false): Promise<Especie[]> {
    if (!this.carga || forzar) {
      this.carga = (async () => {
        const { data, error } = await this.sb.client.from('especies').select('*').order('nombre_comun');
        if (error) {
          this.carga = null;
          throw new Error('No se pudo cargar el catálogo');
        }
        this.especies.set(data as Especie[]);
        return data as Especie[];
      })();
    }
    return this.carga;
  }

  async porId(id: number): Promise<Especie | undefined> {
    const lista = await this.cargar();
    return lista.find((e) => e.id === id) ?? (await this.cargar(true)).find((e) => e.id === id);
  }

  /** El catálogo crece con cada identificación: la próxima consulta lo vuelve a leer. */
  invalidar(): void {
    this.carga = null;
  }
}
