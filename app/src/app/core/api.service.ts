import { Injectable, inject } from '@angular/core';
import { environment } from '../../environments/environment';
import { leerNdjson } from './lector-ndjson';
import { EventoIdentificacion, Observacion, ResultadoIdentificacion } from './modelos';
import { SupabaseService } from './supabase.service';

export type CodigoError =
  | 'sin_conexion'
  | 'servidor_inaccesible'
  | 'subida_fallida'
  | 'sin_sesion'
  | 'foto_ajena'
  | 'limite_diario'
  | 'servicio_saturado'
  | 'foto_no_encontrada'
  | 'ia_no_disponible'
  | 'base_de_datos'
  | 'configuracion_incompleta'
  | 'candidato_invalido'
  | 'especie_desconocida'
  | 'no_en_revision'
  | 'no_encontrada'
  | 'desconocido';

export class ErrorIdentificacion extends Error {
  constructor(
    readonly codigo: CodigoError,
    mensaje: string,
    readonly disponibleEn: string | null = null,
    readonly invitado = false,
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

// La API espera a Claude como máximo 60 s; esto deja margen para la red.
const TIEMPO_MAXIMO_MS = 90_000;
const CONOCIDOS: CodigoError[] = [
  'sin_sesion', 'foto_ajena', 'limite_diario', 'servicio_saturado', 'foto_no_encontrada', 'ia_no_disponible', 'base_de_datos',
  'configuracion_incompleta', 'candidato_invalido', 'especie_desconocida', 'no_en_revision', 'no_encontrada',
];

/** Cliente de la API en Python (identificar, elegir entre especies parecidas y borrar la cuenta). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly sb = inject(SupabaseService);

  private cabeceras(extra: Record<string, string> = {}): Record<string, string> {
    return { 'Content-Type': 'application/json', Authorization: `Bearer ${this.sb.token() ?? ''}`, ...extra };
  }

  /**
   * Identifica la foto ya subida. Avisa cada evento en cuanto llega (`alEvento`): primero lo que la IA va escribiendo,
   * después el resultado guardado y, si la especie es nueva, su ficha. Termina con el resultado.
   */
  async identificar(
    peticion: PeticionIdentificar,
    alEvento: (e: EventoIdentificacion) => void = () => undefined,
    fetchFn: typeof fetch = fetch,
  ): Promise<ResultadoIdentificacion> {
    const respuesta = await this.pedir(fetchFn, '/identificar', {
      method: 'POST',
      headers: this.cabeceras({ Accept: 'application/x-ndjson' }),
      body: JSON.stringify(peticion),
    });
    if (!respuesta.ok) throw aError(respuesta.status, await respuesta.json().catch(() => ({})));

    const fin: { resultado: ResultadoIdentificacion | null; error: ErrorIdentificacion | null } = { resultado: null, error: null };
    const recibir = (e: EventoIdentificacion) => {
      if (e.tipo === 'resultado') fin.resultado = e;
      if (e.tipo === 'error') fin.error = aError(502, { detail: e });
      else alEvento(e);
    };
    try {
      if ((respuesta.headers.get('content-type') ?? '').includes('ndjson') && respuesta.body) {
        await leerNdjson<EventoIdentificacion>(respuesta.body, recibir);
      } else {
        // Versión anterior de la API (o un proxy que junta la respuesta): un solo JSON con el resultado.
        recibir({ tipo: 'resultado', ...(await respuesta.json()) } as EventoIdentificacion);
      }
    } catch (e) {
      // La conexión se cortó a medias: si ya llegó el resultado está guardado; si no, se avisa.
      if (!fin.resultado) throw errorDeRed(e);
    }
    if (fin.error) throw fin.error;
    if (!fin.resultado) {
      throw new ErrorIdentificacion('desconocido', 'La identificación se interrumpió. Revisa tu historial o intenta de nuevo.');
    }
    return fin.resultado;
  }

  /** La persona elige cuál de las especies parecidas es la de su foto. */
  async elegir(observacionId: string, nombreCientifico: string, fetchFn: typeof fetch = fetch): Promise<Observacion> {
    const r = await this.pedir(fetchFn, `/observaciones/${encodeURIComponent(observacionId)}/elegir`, {
      method: 'POST',
      headers: this.cabeceras(),
      body: JSON.stringify({ nombre_cientifico: nombreCientifico }),
    });
    const cuerpo = await r.json().catch(() => ({}));
    if (!r.ok) throw aError(r.status, cuerpo);
    return (cuerpo as { observacion: Observacion }).observacion;
  }

  private async pedir(fetchFn: typeof fetch, ruta: string, init: RequestInit): Promise<Response> {
    try {
      // Después de esto se avisa en vez de esperar sin fin.
      return await fetchFn(`${environment.apiUrl}${ruta}`, { ...init, signal: AbortSignal.timeout(TIEMPO_MAXIMO_MS) });
    } catch (e) {
      throw errorDeRed(e);
    }
  }
}

function errorDeRed(e: unknown): ErrorIdentificacion {
  if ((e as Error)?.name === 'TimeoutError') {
    return new ErrorIdentificacion('ia_no_disponible', 'La identificación tardó demasiado. Intenta de nuevo en un momento.');
  }
  // fetch solo falla así si no hubo respuesta: sin internet, o la API apagada / inalcanzable / bloqueada por CORS.
  if (!estaEnLinea()) return new ErrorIdentificacion('sin_conexion', 'No pudimos enviar tu foto. Revisa tu conexión a internet.');
  return new ErrorIdentificacion(
    'servidor_inaccesible',
    `No pudimos comunicarnos con el servidor de identificación (${environment.apiUrl}). Revisa que la API esté encendida y vuelve a intentarlo.`,
  );
}

export function estaEnLinea(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

export function aError(status: number, cuerpo: unknown): ErrorIdentificacion {
  const detalle = (cuerpo as { detail?: { codigo?: string; mensaje?: string; disponible_en?: string; invitado?: boolean } })?.detail;
  if (detalle?.codigo && (CONOCIDOS as string[]).includes(detalle.codigo)) {
    return new ErrorIdentificacion(detalle.codigo as CodigoError, detalle.mensaje ?? '', detalle.disponible_en ?? null, !!detalle.invitado);
  }
  if (status === 401) return new ErrorIdentificacion('sin_sesion', 'Tu sesión expiró. Vuelve a iniciar sesión.');
  return new ErrorIdentificacion('desconocido', detalle?.mensaje || 'Algo salió mal. Intenta de nuevo.');
}
