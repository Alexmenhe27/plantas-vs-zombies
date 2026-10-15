import { Injectable } from '@angular/core';

/**
 * Foto de referencia de una especie que todavía no está en el catálogo (para "¿Cuál de estas es?").
 * Se toma del resumen de Wikipedia (fotos con licencia libre de Wikimedia Commons). Gratis y sin clave.
 */
@Injectable({ providedIn: 'root' })
export class WikipediaService {
  private readonly cache = new Map<string, Promise<string | null>>();

  foto(nombreCientifico: string): Promise<string | null> {
    let p = this.cache.get(nombreCientifico);
    if (!p) {
      p = this.buscar(nombreCientifico);
      this.cache.set(nombreCientifico, p);
    }
    return p;
  }

  private async buscar(nombre: string): Promise<string | null> {
    const titulo = encodeURIComponent(nombre.replace(/ /g, '_'));
    for (const idioma of ['es', 'en']) {
      try {
        const r = await fetch(`https://${idioma}.wikipedia.org/api/rest_v1/page/summary/${titulo}`, { signal: AbortSignal.timeout(6000) });
        if (!r.ok) continue;
        const datos = (await r.json()) as { thumbnail?: { source?: string } };
        const url = datos.thumbnail?.source;
        if (url && url.includes('/commons/')) return url;
      } catch {
        // Sin foto: se muestra el icono del grupo.
      }
    }
    return null;
  }
}
