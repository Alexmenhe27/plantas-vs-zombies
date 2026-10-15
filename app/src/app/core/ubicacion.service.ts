import { Injectable, signal } from '@angular/core';
import { Geolocation } from '@capacitor/geolocation';

export interface Coordenadas {
  latitud: number;
  longitud: number;
}

const RECIENTE_MS = 5 * 60_000;

/**
 * Ubicación para la pista de la IA. Se empieza a buscar en cuanto la persona toca la cámara (mientras encuadra),
 * así casi siempre está lista cuando la foto termina de subir. Nunca hace esperar más de un momento:
 * si no llega a tiempo, se identifica sin ella. La persona puede apagarla en su perfil.
 */
@Injectable({ providedIn: 'root' })
export class UbicacionService {
  readonly permitida = signal(leerPreferencia());
  private ultima: { coords: Coordenadas; en: number } | null = null;
  private enCurso: Promise<Coordenadas | null> | null = null;

  cambiarPermitida(valor: boolean): void {
    this.permitida.set(valor);
    if (!valor) this.ultima = null;
    try {
      localStorage.setItem('usar-ubicacion', valor ? 'si' : 'no');
    } catch {
      // Sin almacenamiento: la preferencia dura solo esta sesión.
    }
  }

  /** Empieza a buscar la ubicación sin esperar el resultado. */
  precargar(): void {
    if (!this.permitida() || this.enCurso) return;
    if (this.ultima && Date.now() - this.ultima.en < RECIENTE_MS) return;
    this.enCurso = Geolocation.getCurrentPosition({ enableHighAccuracy: false, timeout: 15_000, maximumAge: 120_000 })
      .then((pos) => {
        const coords = { latitud: pos.coords.latitude, longitud: pos.coords.longitude };
        this.ultima = { coords, en: Date.now() };
        return coords;
      })
      .catch(() => null)
      .finally(() => {
        this.enCurso = null;
      });
  }

  /** La ubicación para una foto: la reciente o la que se está buscando, esperando como máximo `esperaMs`. */
  async paraFoto(esperaMs = 1500): Promise<Coordenadas | null> {
    if (!this.permitida()) return null;
    if (this.ultima && Date.now() - this.ultima.en < RECIENTE_MS) return this.ultima.coords;
    this.precargar();
    const enCurso = this.enCurso;
    if (!enCurso) return this.ultima?.coords ?? null;
    // En el navegador el "timeout" no corre mientras el aviso de permiso sigue sin respuesta: por eso el límite propio.
    return Promise.race([enCurso, new Promise<null>((ok) => setTimeout(() => ok(null), esperaMs))]);
  }
}

function leerPreferencia(): boolean {
  try {
    return localStorage.getItem('usar-ubicacion') !== 'no';
  } catch {
    return true;
  }
}
