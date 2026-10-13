import { Injectable, signal } from '@angular/core';

export interface FotoPendiente {
  blob: Blob;
  vistaPrevia: string;
  tomadaEn: string;
}

/** Guarda la foto elegida mientras se pasa de "Inicio" a "Analizando". */
@Injectable({ providedIn: 'root' })
export class IdentificacionService {
  readonly pendiente = signal<FotoPendiente | null>(null);

  poner(blob: Blob): void {
    this.limpiar();
    this.pendiente.set({ blob, vistaPrevia: URL.createObjectURL(blob), tomadaEn: new Date().toISOString() });
  }

  limpiar(): void {
    const p = this.pendiente();
    if (p) URL.revokeObjectURL(p.vistaPrevia);
    this.pendiente.set(null);
  }
}
