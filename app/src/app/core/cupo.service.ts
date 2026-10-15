import { Injectable, inject, signal } from '@angular/core';
import { environment } from '../../environments/environment';
import { Cupo } from './modelos';
import { SupabaseService } from './supabase.service';

/** Cuántas identificaciones le quedan hoy a la persona (la cuenta la lleva la base de datos). */
@Injectable({ providedIn: 'root' })
export class CupoService {
  private readonly sb = inject(SupabaseService);
  readonly cupo = signal<Cupo | null>(null);

  async actualizar(): Promise<Cupo | null> {
    const { data, error } = await this.sb.client.rpc('mi_cupo');
    if (!error && data) {
      const cupo = data as Cupo;
      this.cupo.set(cupo);
      // Un invitado que ya confirmó su correo (quizá en otro dispositivo): se renueva la sesión para que la app lo sepa.
      if (!cupo.invitado && this.sb.esInvitado()) void this.sb.client.auth.refreshSession();
      return cupo;
    }
    // Base de datos sin la migración del 14/10/2026: se usa la función anterior.
    const anterior = await this.sb.client.rpc('identificaciones_restantes');
    if (anterior.error || typeof anterior.data !== 'number') return this.cupo();
    const limite = environment.limiteDiario;
    const c: Cupo = { limite, usadas: limite - anterior.data, restantes: anterior.data, invitado: this.sb.esInvitado(), disponible_en: null };
    this.cupo.set(c);
    return c;
  }

  /** Después de identificar la API ya dice cuántas quedan: no hace falta preguntar otra vez. */
  descontar(restantes: number, limite: number): void {
    const c = this.cupo();
    this.cupo.set({ limite, usadas: limite - restantes, restantes, invitado: c?.invitado ?? this.sb.esInvitado(), disponible_en: null, sin_limite: c?.sin_limite });
  }

  limpiar(): void {
    this.cupo.set(null);
  }
}
