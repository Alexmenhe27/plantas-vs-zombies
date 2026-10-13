import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
import { FotosService } from './fotos.service';
import { Observacion } from './modelos';
import { SupabaseService } from './supabase.service';

export interface Avistamiento {
  id: string;
  ruta_foto: string;
  observada_en: string;
  nombre_usuario: string | null;
  latitud: number | null;
  longitud: number | null;
}

@Injectable({ providedIn: 'root' })
export class ObservacionesService {
  private readonly sb = inject(SupabaseService);
  private readonly fotos = inject(FotosService);

  async mias(): Promise<Observacion[]> {
    const { data, error } = await this.sb.client
      .from('observaciones')
      .select('*, especie:especies(*)')
      .eq('usuario_id', this.sb.userId())
      .order('creado_en', { ascending: false })
      .limit(200);
    if (error) throw new Error('No se pudieron cargar tus observaciones');
    return data as Observacion[];
  }

  async una(id: string): Promise<Observacion | null> {
    const { data, error } = await this.sb.client.from('observaciones').select('*, especie:especies(*)').eq('id', id).maybeSingle();
    if (error) throw new Error('No se pudo cargar la observación');
    return data as Observacion | null;
  }

  async cambiarPublica(id: string, isPublic: boolean): Promise<void> {
    const { error } = await this.sb.client.from('observaciones').update({ es_publica: isPublic }).eq('id', id);
    if (error) throw new Error('No se pudo guardar el cambio');
  }

  async borrar(obs: Observacion): Promise<void> {
    const { error } = await this.sb.client.from('observaciones').delete().eq('id', obs.id);
    if (error) throw new Error('No se pudo borrar');
    await this.fotos.borrar(obs.ruta_foto);
  }

  /** Cuántas identificaciones le quedan hoy (función en la base de datos). */
  async restantes(): Promise<number> {
    const { data, error } = await this.sb.client.rpc('identificaciones_restantes');
    if (error || typeof data !== 'number') return environment.limiteDiario;
    return data;
  }

  /** Avistamientos públicos recientes de una especie (ubicación aproximada si está protegida). */
  async avistamientos(especieId: number, limite = 5): Promise<Avistamiento[]> {
    const { data } = await this.sb.client
      .from('observaciones_publicas')
      .select('id, ruta_foto, observada_en, nombre_usuario, latitud, longitud')
      .eq('especie_id', especieId)
      .order('observada_en', { ascending: false })
      .limit(limite);
    return (data ?? []) as Avistamiento[];
  }
}
