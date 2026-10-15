import { Share } from '@capacitor/share';
import { ToastController } from '@ionic/angular';
import { Observacion } from '../core/modelos';

/** Comparte el descubrimiento (en el teléfono abre el menú de compartir; en la computadora copia el texto). */
export async function compartirObservacion(o: Observacion, toast: ToastController): Promise<void> {
  const nombre = o.especie?.nombre_comun ?? o.ia_nombre_sugerido ?? 'una especie';
  const cientifico = o.especie ? ` (${o.especie.nombre_cientifico})` : '';
  const texto = `Encontré ${nombre}${cientifico} y la identifiqué con Fauna y Flora.`;
  try {
    if ((await Share.canShare()).value) {
      await Share.share({ title: 'Fauna y Flora', text: texto, dialogTitle: 'Compartir descubrimiento' });
      return;
    }
  } catch (e) {
    if (String((e as Error)?.message ?? e).toLowerCase().includes('cancel')) return;
  }
  let mensaje = 'Texto copiado: pégalo donde quieras compartirlo.';
  try {
    await navigator.clipboard.writeText(texto);
  } catch {
    mensaje = 'No se pudo compartir desde este navegador.';
  }
  await (await toast.create({ message: mensaje, duration: 2500, color: 'dark' })).present();
}
