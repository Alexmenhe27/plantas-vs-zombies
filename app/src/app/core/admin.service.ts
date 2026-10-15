import { Injectable, inject } from '@angular/core';
import { CatalogoService } from './catalogo.service';
import { Especie, EstadoObservacion, Observacion } from './modelos';
import { SupabaseService } from './supabase.service';

export interface ObservacionRevision extends Observacion {
  perfil: { nombre_usuario: string | null } | null;
}

/** Panel de revisión (solo administradores; los permisos los vuelve a comprobar la base de datos con RLS). */
@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly sb = inject(SupabaseService);
  private readonly catalogo = inject(CatalogoService);

  /** Lo que la IA no supo (en revisión) y lo que eligió la persona entre las parecidas (por confirmar). */
  async porRevisar(): Promise<ObservacionRevision[]> {
    const { data, error } = await this.sb.client
      .from('observaciones')
      .select('*, especie:especies(*), perfil:perfiles(nombre_usuario)')
      .in('estado', ['revisar', 'elegida'])
      .order('creado_en', { ascending: false })
      .limit(60);
    if (error) throw new Error('No se pudieron cargar las observaciones por revisar');
    return data as ObservacionRevision[];
  }

  /** Fichas creadas por la IA, pendientes de que una persona las revise. */
  async especiesSinVerificar(): Promise<Especie[]> {
    const { data, error } = await this.sb.client.from('especies').select('*').eq('verificada', false).order('creado_en', { ascending: false }).limit(100);
    if (error) throw new Error('No se pudieron cargar las especies');
    return data as Especie[];
  }

  /** Confirma o corrige la especie de una observación. */
  async corregir(observacionId: string, especieId: number | null, estado: EstadoObservacion): Promise<void> {
    const { error } = await this.sb.client.from('observaciones').update({ especie_id: especieId, estado }).eq('id', observacionId);
    if (error) throw new Error('No se pudo guardar la corrección');
  }

  async guardarEspecie(id: number, campos: Partial<Especie>): Promise<void> {
    const { error } = await this.sb.client.from('especies').update(campos).eq('id', id);
    if (error) throw new Error('No se pudo guardar la especie');
    this.catalogo.invalidar();
  }

  async borrarEspecie(id: number): Promise<void> {
    const { error } = await this.sb.client.from('especies').delete().eq('id', id);
    if (error) throw new Error('No se pudo borrar la especie');
    this.catalogo.invalidar();
  }
}
