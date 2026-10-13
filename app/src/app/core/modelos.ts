export type Reino = 'animal' | 'planta';
export type EstadoObservacion = 'identificada' | 'revisar' | 'corregida' | 'no_identificada';

export interface Especie {
  id: number;
  nombre_comun: string;
  nombre_cientifico: string;
  reino: Reino;
  grupo: string;
  familia: string | null;
  protegida: boolean;
  categoria_nom059: 'P' | 'A' | 'Pr' | 'E' | null;
  introducida: boolean;
  descripcion: string | null;
  habitat: string | null;
  alimentacion: string | null;
  tamano: string | null;
  imagen_url: string | null;
  imagen_fuente: string | null;
  /** false = ficha creada por la IA, pendiente de revisión. */
  verificada: boolean;
}

export interface Candidato {
  /** null si la especie todavía no está en el catálogo. */
  especie_id: number | null;
  nombre_cientifico?: string;
  nombre_comun?: string | null;
  confianza: number;
}

export interface Observacion {
  id: string;
  usuario_id: string;
  ruta_foto: string;
  latitud: number | null;
  longitud: number | null;
  observada_en: string;
  especie_id: number | null;
  ia_confianza: number | null;
  ia_explicacion: string | null;
  ia_nombre_sugerido: string | null;
  ia_candidatos: Candidato[];
  ia_problema: 'borrosa' | 'sin_organismo' | null;
  estado: EstadoObservacion;
  es_publica: boolean;
  creado_en: string;
  especie?: Especie | null;
}

export interface Perfil {
  id: string;
  nombre_usuario: string | null;
  rol: 'usuario' | 'admin';
  creado_en: string;
}
