import { Capacitor } from '@capacitor/core';
import { Haptics, ImpactStyle, NotificationType } from '@capacitor/haptics';

/** Vibración corta en el teléfono (en el navegador no hace nada). Nunca falla. */
export async function vibrarExito(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await Haptics.notification({ type: NotificationType.Success }).catch(() => undefined);
}

export async function vibrarToque(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await Haptics.impact({ style: ImpactStyle.Light }).catch(() => undefined);
}
