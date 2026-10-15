import { Injectable, inject, signal } from '@angular/core';
import { Especie, EspecieResumen } from './modelos';
import { SupabaseService } from './supabase.service';

/** Columnas que necesitan las listas (la ficha completa se pide aparte): así se descarga mucho menos. */
export const CAMPOS_RESUMEN = 'id,nombre_comun,nombre_cientifico,reino,grupo,protegida,categoria_nom059,introducida,imagen_url,verificada';
export const POR_PAGINA = 24;

export interface FiltroCatalogo {
  texto?: string;
  grupo?: string | null;
  soloProtegidas?: boolean;
}

/** Quita acentos y mayúsculas (igual que la columna "busqueda" de la base de datos). */
export function normalizar(t: string): string {
  return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/**
 * Catálogo de especies. La búsqueda y los filtros se hacen en la base de datos y por páginas: el catálogo crece solo
 * con cada especie nueva que alguien fotografía, así que ya no se descarga completo.
 */
@Injectable({ providedIn: 'root' })
export class CatalogoService {
  private readonly sb = inject(SupabaseService);
  private readonly fichas = new Map<number, Especie>();
  /** Cambia cuando el catálogo crece (una identificación agregó una especie). */
  readonly version = signal(0);

  async buscar(filtro: FiltroCatalogo, desde = 0): Promise<{ especies: EspecieResumen[]; total: number | null }> {
    const texto = normalizar((filtro.texto ?? '').trim()).replace(/[%_,()]/g, ' ').trim();
    const consulta = (conColumnaBusqueda: boolean) => {
      let q = this.sb.client
        .from('especies')
        .select(CAMPOS_RESUMEN, { count: desde === 0 ? 'exact' : undefined })
        .order('nombre_comun')
        .range(desde, desde + POR_PAGINA - 1);
      if (texto) {
        q = conColumnaBusqueda
          ? q.ilike('busqueda', `%${texto}%`)
          : q.or(`nombre_comun.ilike.%${texto}%,nombre_cientifico.ilike.%${texto}%`);
      }
      if (filtro.grupo === 'planta') q = q.eq('reino', 'planta');
      else if (filtro.grupo) q = q.eq('grupo', filtro.grupo);
      if (filtro.soloProtegidas) q = q.eq('protegida', true);
      return q;
    };
    let { data, error, count } = await consulta(true);
    if (error && texto) {
      // Base de datos sin la columna "busqueda" (antes de la migración del 14/10/2026).
      ({ data, error, count } = await consulta(false));
    }
    if (error) throw new Error('No se pudo cargar el catálogo');
    return { especies: (data ?? []) as EspecieResumen[], total: count ?? null };
  }

  async porId(id: number): Promise<Especie | null> {
    const guardada = this.fichas.get(id);
    if (guardada) return guardada;
    const { data, error } = await this.sb.client.from('especies').select('*').eq('id', id).maybeSingle();
    if (error) throw new Error('No se pudo cargar la especie');
    if (data) this.fichas.set(id, data as Especie);
    return (data as Especie) ?? null;
  }

  async porIds(ids: number[]): Promise<Especie[]> {
    const faltan = [...new Set(ids)].filter((id) => !this.fichas.has(id));
    if (faltan.length) {
      const { data } = await this.sb.client.from('especies').select('*').in('id', faltan);
      for (const e of (data ?? []) as Especie[]) this.fichas.set(e.id, e);
    }
    return ids.map((id) => this.fichas.get(id)).filter((e): e is Especie => !!e);
  }

  /** La ficha de una especie nueva llegó (o cambió): se actualiza en memoria. */
  actualizar(especie: Especie): void {
    this.fichas.set(especie.id, especie);
  }

  invalidar(): void {
    this.fichas.clear();
    this.version.update((v) => v + 1);
  }
}
