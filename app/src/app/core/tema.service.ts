import { Injectable, signal } from '@angular/core';

/** La app usa siempre el modo oscuro. */
@Injectable({ providedIn: 'root' })
export class TemaService {
  readonly oscuro = signal(true);

  constructor() {
    document.documentElement.classList.add('ion-palette-dark');
  }
}
