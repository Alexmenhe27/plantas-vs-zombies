import { addIcons } from 'ionicons';
import {
  albumsOutline, arrowBack, arrowForward, calendarOutline, cameraOutline, checkmark, checkmarkCircle, checkmarkDoneOutline,
  chevronForward, close, cloudDoneOutline, cloudOfflineOutline, cloudUploadOutline, createOutline, earthOutline, eyeOffOutline,
  eyeOutline, flagOutline, flashOutline, flowerOutline, footstepsOutline, gridOutline, handLeftOutline, helpCircleOutline, homeOutline,
  hourglassOutline, imageOutline, imagesOutline, informationCircleOutline, leafOutline, locationOutline, lockClosedOutline,
  logOutOutline, mapOutline, moonOutline, personAddOutline, personOutline, phonePortraitOutline, refreshOutline, resizeOutline,
  restaurantOutline, ribbonOutline, scanOutline, searchOutline, shareSocialOutline, shieldCheckmarkOutline, sparklesOutline,
  sunnyOutline, timeOutline, trashOutline, warningOutline,
} from 'ionicons/icons';

/** Iconos de trazo propios (grupos y pestañas), con el mismo estilo de los de ionicons. */
function svg(trazos: string): string {
  const s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${trazos}</svg>`;
  // ionicons lee el SVG directamente del texto del data URL, por eso va sin codificar.
  return `data:image/svg+xml;utf8,${s}`;
}

export function registrarIconos(): void {
  addIcons({
    albumsOutline, arrowBack, arrowForward, calendarOutline, cameraOutline, checkmark, checkmarkCircle, checkmarkDoneOutline,
    chevronForward, close, cloudDoneOutline, cloudOfflineOutline, cloudUploadOutline, createOutline, earthOutline, eyeOffOutline,
    eyeOutline, flagOutline, flashOutline, flowerOutline, footstepsOutline, gridOutline, handLeftOutline, helpCircleOutline, homeOutline,
    hourglassOutline, imageOutline, imagesOutline, informationCircleOutline, leafOutline, locationOutline, lockClosedOutline,
    logOutOutline, mapOutline, moonOutline, personAddOutline, personOutline, phonePortraitOutline, refreshOutline, resizeOutline,
    restaurantOutline, ribbonOutline, scanOutline, searchOutline, shareSocialOutline, shieldCheckmarkOutline, sparklesOutline,
    sunnyOutline, timeOutline, trashOutline, warningOutline,
    'grupo-ave': svg('<path d="M16 7h.01"/><path d="M3.5 18H11a7 7 0 007-7V7a3 3 0 00-5.5-1.7L3.5 18z"/><path d="M20 7l2 .5-2 .5"/><path d="M10 18v3M14 17.5V21"/>'),
    'grupo-mamifero': svg('<circle cx="5.5" cy="10" r="1.8"/><circle cx="9.5" cy="6" r="1.8"/><circle cx="14.5" cy="6" r="1.8"/><circle cx="18.5" cy="10" r="1.8"/><path d="M8 17c0-2.5 1.8-5 4-5s4 2.5 4 5c0 1.7-1.3 3-3 3h-2c-1.7 0-3-1.3-3-3z"/>'),
    'grupo-reptil': svg('<path d="M4 20h9a3 3 0 000-6H9a3 3 0 010-6h6"/><path d="M15 8h3l2-2"/>'),
    'grupo-anfibio': svg('<circle cx="8" cy="7" r="2.5"/><circle cx="16" cy="7" r="2.5"/><path d="M4 14c0-3 3.5-5 8-5s8 2 8 5-3.5 5-8 5-8-2-8-5z"/><path d="M9 14c1.5 1 4.5 1 6 0"/>'),
    'grupo-insecto': svg('<path d="M12 7v12"/><path d="M12 10C10 5 4 3 3.5 6.5S6 13 12 12"/><path d="M12 10c2-5 8-7 8.5-3.5S18 13 12 12"/><path d="M12 13c-3 0-6 2-5 5s4 0 5-3M12 13c3 0 6 2 5 5s-4 0-5-3"/>'),
    'grupo-pez': svg('<path d="M3 12c3-4 7-6 11-6 3 0 5 3 6 6-1 3-3 6-6 6-4 0-8-2-11-6z"/><path d="M3 12l-1-4M3 12l-1 4"/><path d="M16 11h.01"/>'),
    'grupo-planta': svg('<path d="M5 19c0-8 6-14 14-14 0 8-6 14-14 14z"/><path d="M5 19l7-7"/>'),
    'tab-identificar': svg('<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>'),
    'tab-explorar': svg('<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2 5-5 2 2-5z"/>'),
    'tab-coleccion': svg('<path d="M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3z"/><path d="M5 17a3 3 0 013-3h11"/><path d="M10 11c0-2.8 2-4.8 4.8-4.8 0 2.8-2 4.8-4.8 4.8z"/>'),
    'tab-perfil': svg('<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>'),
  });
}
