import { Injectable, inject } from '@angular/core';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import { SupabaseService } from './supabase.service';

export const BUCKET = 'fotos';
const LADO_MAXIMO = 1024; // suficiente para identificar; la foto pesa ~4 veces menos que a 1600 px

/** Cámara/galería, compresión (quita EXIF) y subida al bucket privado. */
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
  async comprimir(original: Blob): Promise<Blob> {
    const bitmap = await createImageBitmap(original);
    const escala = Math.min(1, LADO_MAXIMO / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * escala);
    canvas.height = Math.round(bitmap.height * escala);
    canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    return await new Promise<Blob>((ok, mal) =>
      canvas.toBlob((b) => (b ? ok(b) : mal(new Error('No se pudo procesar la foto'))), 'image/jpeg', 0.8),
    );
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

  /** Enlaces temporales (1 hora) para mostrar fotos privadas; se guardan en memoria. */
  async urlsFirmadas(rutas: string[]): Promise<Record<string, string>> {
    const ahora = Date.now();
    const resultado: Record<string, string> = {};
    const faltan: string[] = [];
    for (const r of new Set(rutas)) {
      const c = this.urls.get(r);
      if (c && c.vence > ahora) resultado[r] = c.url;
      else faltan.push(r);
    }
    if (faltan.length) {
      const { data } = await this.sb.client.storage.from(BUCKET).createSignedUrls(faltan, 3600);
      for (const d of data ?? []) {
        if (d.signedUrl && d.path) {
          resultado[d.path] = d.signedUrl;
          this.urls.set(d.path, { url: d.signedUrl, vence: ahora + 50 * 60 * 1000 });
        }
      }
    }
    return resultado;
  }

  async borrar(ruta: string): Promise<void> {
    await this.sb.client.storage.from(BUCKET).remove([ruta]);
    this.urls.delete(ruta);
  }
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
