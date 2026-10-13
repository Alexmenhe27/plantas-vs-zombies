import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
import { Observacion } from './modelos';
import { SupabaseService } from './supabase.service';

export type CodigoError =
  | 'sin_conexion'
  | 'servidor_inaccesible'
  | 'subida_fallida'
  | 'sin_sesion'
  | 'foto_ajena'
  | 'limite_diario'
  | 'foto_no_encontrada'
  | 'ia_no_disponible'
  | 'base_de_datos'
  | 'configuracion_incompleta'
  | 'desconocido';

export class ErrorIdentificacion extends Error {
  constructor(
    readonly codigo: CodigoError,
    mensaje: string,
    readonly disponibleEn: string | null = null,
  ) {
    super(mensaje);
  }
}

export interface PeticionIdentificar {
  ruta_foto: string;
  latitud: number | null;
  longitud: number | null;
  observada_en: string;
}

export interface RespuestaIdentificar {
  observacion: Observacion;
  restantes: number;
}

// La API espera a Gemini como máximo ~110 s en total (probando modelos de respaldo); esto deja margen para la red.
const TIEMPO_MAXIMO_MS = 150_000;

/** Cliente de la API en Python (solo para identificar). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly sb = inject(SupabaseService);

  async identificar(peticion: PeticionIdentificar, fetchFn: typeof fetch = fetch): Promise<RespuestaIdentificar> {
    let respuesta: Response;
    try {
      respuesta = await fetchFn(`${environment.apiUrl}/identificar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${this.sb.token() ?? ''}` },
        body: JSON.stringify(peticion),
        // Después de esto se avisa en vez de esperar sin fin.
        signal: AbortSignal.timeout(TIEMPO_MAXIMO_MS),
      });
    } catch (e) {
      if ((e as Error)?.name === 'TimeoutError') {
        throw new ErrorIdentificacion('ia_no_disponible', 'La identificación tardó demasiado. Intenta de nuevo en un momento.');
      }
      // fetch solo falla así si no hubo respuesta: sin internet, o la API apagada / inalcanzable / bloqueada por CORS.
      if (!estaEnLinea()) throw new ErrorIdentificacion('sin_conexion', 'No pudimos enviar tu foto. Revisa tu conexión a internet.');
      throw new ErrorIdentificacion(
        'servidor_inaccesible',
        `No pudimos comunicarnos con el servidor de identificación (${environment.apiUrl}). Revisa que la API esté encendida y vuelve a intentarlo.`,
      );
    }
    const cuerpo = await respuesta.json().catch(() => ({}));
    if (respuesta.ok) return cuerpo as RespuestaIdentificar;
    throw aError(respuesta.status, cuerpo);
  }
}

export function estaEnLinea(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

export function aError(status: number, cuerpo: unknown): ErrorIdentificacion {
  const detalle = (cuerpo as { detail?: { codigo?: string; mensaje?: string; disponible_en?: string } })?.detail;
  const conocidos: CodigoError[] = [
    'sin_sesion', 'foto_ajena', 'limite_diario', 'foto_no_encontrada', 'ia_no_disponible', 'base_de_datos', 'configuracion_incompleta',
  ];
  if (detalle?.codigo && (conocidos as string[]).includes(detalle.codigo)) {
    return new ErrorIdentificacion(detalle.codigo as CodigoError, detalle.mensaje ?? '', detalle.disponible_en ?? null);
  }
  if (status === 401) return new ErrorIdentificacion('sin_sesion', 'Tu sesión expiró. Vuelve a iniciar sesión.');
  return new ErrorIdentificacion('desconocido', detalle?.mensaje || 'Algo salió mal. Intenta de nuevo.');
}
