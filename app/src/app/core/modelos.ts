export type Reino = 'animal' | 'planta';
/** identificada: la IA está segura · revisar: la IA duda · elegida: la persona eligió entre las parecidas · corregida: por un admin */
export type EstadoObservacion = 'identificada' | 'revisar' | 'elegida' | 'corregida' | 'no_identificada';

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
  gbif_id?: number | null;
}

/** Lo que se muestra en listas (columnas ligeras). */
export type EspecieResumen = Pick<
  Especie,
  'id' | 'nombre_comun' | 'nombre_cientifico' | 'reino' | 'grupo' | 'protegida' | 'categoria_nom059' | 'introducida' | 'imagen_url' | 'verificada'
>;

export interface Candidato {
  /** null si la especie todavía no está en el catálogo. */
  especie_id: number | null;
  nombre_cientifico?: string;
  nombre_comun?: string | null;
  grupo?: string | null;
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
  publicar_por_defecto: boolean;
}

export interface Cupo {
  limite: number;
  usadas: number;
  restantes: number;
  invitado: boolean;
  disponible_en: string | null;
  /** Administradores: sin límite de identificaciones. */
  sin_limite?: boolean;
}

/** Una especie de la colección de la persona (función mi_coleccion). */
export interface EspecieColeccion {
  especie: Especie;
  veces: number;
  primera_vez: string;
  ultima_vez: string;
  ruta_foto: string;
}

export interface Avistamiento {
  id: string;
  ruta_foto: string;
  observada_en: string;
  especie_id: number;
  estado: EstadoObservacion;
  nombre_usuario: string | null;
  /** Aproximada (~10 km); null si la especie está protegida. */
  latitud: number | null;
  longitud: number | null;
  nombre_comun: string;
  nombre_cientifico: string;
  grupo: string;
  reino: Reino;
  protegida: boolean;
}

/** Lo que Claude ya escribió mientras identifica (llega por partes). */
export interface Parcial {
  problema?: 'ninguno' | 'borrosa' | 'sin_organismo';
  nombre_comun?: string | null;
  nombre_cientifico?: string | null;
  reino?: Reino | null;
  grupo?: string | null;
  confianza?: number;
  explicacion?: string;
}

export interface ResultadoIdentificacion {
  observacion: Observacion;
  restantes: number;
  limite: number;
  candidatos_especies: Especie[];
  ficha_pendiente: boolean;
}

/** Eventos de POST /identificar con Accept: application/x-ndjson (uno por línea). */
export type EventoIdentificacion =
  | ({ tipo: 'parcial' } & Parcial)
  | ({ tipo: 'resultado' } & ResultadoIdentificacion)
  | { tipo: 'ficha'; especie: Especie }
  | { tipo: 'error'; codigo: string; mensaje: string }
  | { tipo: 'fin'; tiempos: Record<string, number> };
