import { Injectable, inject } from '@angular/core';
import { CAMPOS_RESUMEN } from './catalogo.service';
import { FotosService } from './fotos.service';
import { Avistamiento, EspecieColeccion, Observacion } from './modelos';
import { SupabaseService } from './supabase.service';

export const POR_PAGINA_OBS = 30;

@Injectable({ providedIn: 'root' })
export class ObservacionesService {
  private readonly sb = inject(SupabaseService);
  private readonly fotos = inject(FotosService);

  /** Mis observaciones, de la más reciente a la más antigua, por páginas. */
  async mias(desde = 0, cuantas = POR_PAGINA_OBS): Promise<Observacion[]> {
    const { data, error } = await this.sb.client
      .from('observaciones')
      .select(`*, especie:especies(${CAMPOS_RESUMEN})`)
      .eq('usuario_id', this.sb.userId())
      .order('creado_en', { ascending: false })
      .range(desde, desde + cuantas - 1);
    if (error) throw new Error('No se pudieron cargar tus observaciones');
    return data as Observacion[];
  }

  /** Mis observaciones con ubicación (exacta: solo las ve la propia persona), para su mapa. */
  async miasConUbicacion(): Promise<Observacion[]> {
    const { data } = await this.sb.client
      .from('observaciones')
      .select(`id, ruta_foto, latitud, longitud, observada_en, estado, especie:especies(${CAMPOS_RESUMEN})`)
      .eq('usuario_id', this.sb.userId())
      .not('latitud', 'is', null)
      .not('especie_id', 'is', null)
      .order('observada_en', { ascending: false })
      .limit(500);
    return (data ?? []) as unknown as Observacion[];
  }

  async una(id: string): Promise<Observacion | null> {
    const { data, error } = await this.sb.client.from('observaciones').select('*, especie:especies(*)').eq('id', id).maybeSingle();
    if (error) throw new Error('No se pudo cargar la observación');
    return data as Observacion | null;
  }

  async cambiarPublica(id: string, publica: boolean): Promise<void> {
    const { error } = await this.sb.client.from('observaciones').update({ es_publica: publica }).eq('id', id);
    if (error) throw new Error('No se pudo guardar el cambio');
  }

  async borrar(obs: Pick<Observacion, 'id' | 'ruta_foto'>): Promise<void> {
    const { error } = await this.sb.client.from('observaciones').delete().eq('id', obs.id);
    if (error) throw new Error('No se pudo borrar');
    await this.fotos.borrar(obs.ruta_foto);
  }

  /** "No es correcto": manda la observación a revisión para elegir otra especie o que la revise un experto. */
  async marcarParaRevision(id: string): Promise<void> {
    const { error } = await this.sb.client.rpc('marcar_para_revision', { p_id: id });
    if (error) throw new Error('No se pudo mandar a revisión');
  }

  /** Especies que la persona ha encontrado, con cuántas veces y su foto más reciente. */
  async coleccion(): Promise<EspecieColeccion[]> {
    const { data, error } = await this.sb.client.rpc('mi_coleccion');
    if (!error) return (data ?? []) as EspecieColeccion[];
    // Sin la función (base de datos anterior): se arma con las observaciones.
    const mapa = new Map<number, EspecieColeccion>();
    for (const o of await this.mias(0, 500)) {
      if (!o.especie || !['identificada', 'elegida', 'corregida'].includes(o.estado)) continue;
      const c = mapa.get(o.especie.id);
      if (c) {
        c.veces++;
        c.primera_vez = o.observada_en < c.primera_vez ? o.observada_en : c.primera_vez;
      } else {
        mapa.set(o.especie.id, { especie: o.especie, veces: 1, primera_vez: o.observada_en, ultima_vez: o.observada_en, ruta_foto: o.ruta_foto });
      }
    }
    return [...mapa.values()];
  }

  /** Avistamientos públicos (ubicación aproximada; sin ubicación en especies protegidas). */
  async avistamientos(especieId: number | null, limite = 50): Promise<Avistamiento[]> {
    const { data, error } = await this.sb.client.rpc('avistamientos_publicos', { p_especie_id: especieId, p_limite: limite });
    if (!error) return (data ?? []) as Avistamiento[];
    if (especieId === null) return [];
    // Base de datos anterior: vista observaciones_publicas.
    const anterior = await this.sb.client
      .from('observaciones_publicas')
      .select('id, ruta_foto, observada_en, especie_id, nombre_usuario, latitud, longitud')
      .eq('especie_id', especieId)
      .order('observada_en', { ascending: false })
      .limit(limite);
    return (anterior.data ?? []) as Avistamiento[];
  }
}
