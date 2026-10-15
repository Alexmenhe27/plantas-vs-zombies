import { Injectable, inject } from '@angular/core';
import { Camera, CameraDirection, CameraResultType, CameraSource } from '@capacitor/camera';
import { SupabaseService } from './supabase.service';

export const BUCKET = 'fotos';
const LADO_MAXIMO = 1024; // suficiente para identificar; la foto pesa ~4 veces menos que a 1600 px
const LADO_MINIATURA = 320; // para listas y tarjetas: ~15 KB en vez de ~200 KB

/** Ruta de la miniatura de una foto: <usuario>/<id>.mini.jpg */
export function rutaMini(ruta: string): string {
  return ruta.replace(/\.jpg$/, '.mini.jpg');
}

/** Cámara/galería, compresión (quita EXIF), miniaturas y subida al bucket privado. */
@Injectable({ providedIn: 'root' })
export class FotosService {
  private readonly sb = inject(SupabaseService);
  private readonly urls = new Map<string, { url: string; vence: number }>();

  /** Abre la cámara o la galería. Devuelve null si la persona cancela. */
  async elegir(origen: 'camara' | 'galeria'): Promise<Blob | null> {
    try {
      const foto = await Camera.getPhoto({
        source: origen === 'camara' ? CameraSource.Camera : CameraSource.Photos,
        resultType: CameraResultType.Uri,
        quality: 85,
        correctOrientation: true,
        // En el navegador del teléfono abre directo la cámara trasera (sin la pantalla intermedia de PWA Elements).
        webUseInput: true,
        direction: CameraDirection.Rear,
        promptLabelHeader: 'Foto',
        promptLabelPhoto: 'Elegir de la galería',
        promptLabelPicture: 'Tomar foto',
        promptLabelCancel: 'Cancelar',
      });
      if (!foto.webPath) return null;
      return await (await fetch(foto.webPath)).blob();
    } catch (e) {
      const msg = String((e as Error)?.message ?? e).toLowerCase();
      if (msg.includes('cancel')) return null;
      throw e;
    }
  }

  /** Redimensiona a 1024 px y re-codifica en JPEG; al pasar por canvas se pierden los metadatos EXIF (incluido el GPS). */
  comprimir(original: Blob): Promise<Blob> {
    return redimensionar(original, LADO_MAXIMO, 0.8);
  }

  miniatura(foto: Blob): Promise<Blob> {
    return redimensionar(foto, LADO_MINIATURA, 0.72);
  }

  /** Sube la foto a fotos/<usuario_id>/<uuid>.jpg y devuelve la ruta. */
  async subir(foto: Blob): Promise<string> {
    const userId = this.sb.userId();
    if (!userId) throw new Error('Sin sesión');
    const ruta = `${userId}/${idAleatorio()}.jpg`;
    const { error } = await this.sb.client.storage.from(BUCKET).upload(ruta, foto, { contentType: 'image/jpeg', upsert: false });
    if (error) throw new Error(motivoSubida(error.message));
    return ruta;
  }

  /** Sube la miniatura después de la foto (no retrasa la identificación). Si falla, las listas usan la foto completa. */
  async subirMiniatura(ruta: string, foto: Blob): Promise<void> {
    try {
      const mini = await this.miniatura(foto);
      await this.sb.client.storage.from(BUCKET).upload(rutaMini(ruta), mini, { contentType: 'image/jpeg', upsert: false });
    } catch {
      // Sin miniatura no pasa nada.
    }
  }

  /** Enlaces temporales (1 hora) para mostrar fotos privadas; se guardan en memoria. */
  async urlsFirmadas(rutas: string[]): Promise<Record<string, string>> {
    const ahora = Date.now();
    const resultado: Record<string, string> = {};
    const faltan: string[] = [];
    for (const r of new Set(rutas.filter(Boolean))) {
      const c = this.urls.get(r);
      if (c && c.vence > ahora) resultado[r] = c.url;
      else faltan.push(r);
    }
    for (let i = 0; i < faltan.length; i += 100) {
      const { data } = await this.sb.client.storage.from(BUCKET).createSignedUrls(faltan.slice(i, i + 100), 3600);
      for (const d of data ?? []) {
        if (d.signedUrl && d.path) {
          resultado[d.path] = d.signedUrl;
          this.urls.set(d.path, { url: d.signedUrl, vence: ahora + 50 * 60 * 1000 });
        }
      }
    }
    return resultado;
  }

  /** Enlaces de la miniatura y de la foto completa (la miniatura puede no existir en fotos anteriores). */
  async urlsConMiniatura(rutas: string[]): Promise<Record<string, { mini: string | null; completa: string | null }>> {
    const urls = await this.urlsFirmadas(rutas.flatMap((r) => [r, rutaMini(r)]));
    return Object.fromEntries(rutas.map((r) => [r, { mini: urls[rutaMini(r)] ?? null, completa: urls[r] ?? null }]));
  }

  async borrar(ruta: string): Promise<void> {
    await this.sb.client.storage.from(BUCKET).remove([ruta, rutaMini(ruta)]);
    this.urls.delete(ruta);
    this.urls.delete(rutaMini(ruta));
  }
}

async function redimensionar(original: Blob, lado: number, calidad: number): Promise<Blob> {
  const bitmap = await createImageBitmap(original);
  const escala = Math.min(1, lado / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * escala);
  canvas.height = Math.round(bitmap.height * escala);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return await new Promise<Blob>((ok, mal) =>
    canvas.toBlob((b) => (b ? ok(b) : mal(new Error('No se pudo procesar la foto'))), 'image/jpeg', calidad),
  );
}

/** crypto.randomUUID solo existe en https o localhost; al abrir la app desde el cel por la red local (http) no está. */
function idAleatorio(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
}

/** Explica en español por qué Supabase Storage rechazó la foto. */
export function motivoSubida(mensaje: string): string {
  const m = mensaje.toLowerCase();
  if (m.includes('row-level security') || m.includes('unauthorized') || m.includes('jwt'))
    return 'Tu sesión no tiene permiso para guardar la foto. Cierra sesión y vuelve a entrar.';
  if (m.includes('bucket not found')) return 'No existe el almacén de fotos en Supabase (bucket "fotos").';
  if (m.includes('mime') || m.includes('content type')) return 'Ese formato de imagen no está permitido. Usa JPG o PNG.';
  if (m.includes('exceeded') || m.includes('too large') || m.includes('payload')) return 'La foto es demasiado pesada (máximo 5 MB).';
  if (m.includes('fetch') || m.includes('network')) return 'No pudimos conectar con el almacén de fotos. Revisa tu conexión.';
  return `No pudimos guardar tu foto: ${mensaje}`;
}
