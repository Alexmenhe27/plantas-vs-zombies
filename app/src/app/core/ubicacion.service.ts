import { Injectable } from '@angular/core';
import { Geolocation } from '@capacitor/geolocation';

export interface Coordenadas {
  latitud: number;
  longitud: number;
}

@Injectable({ providedIn: 'root' })
export class UbicacionService {
  /** Ubicación actual o null si no hay permiso / GPS apagado. */
  async actual(esperaMaxima = 12000): Promise<Coordenadas | null> {
    const pedir = Geolocation.getCurrentPosition({ enableHighAccuracy: false, timeout: 10000, maximumAge: 120000 })
      .then((pos) => ({ latitud: pos.coords.latitude, longitud: pos.coords.longitude }))
      .catch(() => null);
    // En el navegador el "timeout" no corre mientras el aviso de permiso sigue sin respuesta: sin esto la app se quedaba esperando.
    const limite = new Promise<null>((ok) => setTimeout(() => ok(null), esperaMaxima));
    return Promise.race([pedir, limite]);
  }
}
