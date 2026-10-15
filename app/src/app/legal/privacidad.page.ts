import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { IonContent, IonIcon, NavController } from '@ionic/angular';

/** Aviso de privacidad y términos de uso, en lenguaje claro. */
@Component({
  selector: 'app-privacidad',
  imports: [IonContent, IonIcon],
  template: `
    <ion-content>
      <div class="pagina">
        <button class="boton-icono" type="button" aria-label="Volver" (click)="volver()"><ion-icon name="arrow-back" /></button>
        <header class="pagina-titulo">
          <h1>Privacidad y términos</h1>
          <p>Lo importante, sin letra chiquita. Última actualización: 14 de octubre de 2026.</p>
        </header>

        <section class="tarjeta">
          <h2><ion-icon name="images-outline" />Tus fotos</h2>
          <p>Se guardan en un almacén privado. Antes de subirlas, la app las reduce y les quita los datos ocultos (EXIF), incluida la ubicación
            que guarda la cámara. Solo tú puedes verlas, salvo que publiques una observación.</p>
        </section>

        <section class="tarjeta">
          <h2><ion-icon name="location-outline" />Tu ubicación</h2>
          <p>Es opcional y puedes apagarla en tu perfil. Si la das, se usa como pista para identificar mejor y se guarda con tu observación.
            Tu ubicación exacta solo la ves tú. Si publicas una observación, los demás ven una ubicación aproximada (unos 10 km);
            en especies protegidas no se muestra ninguna ubicación.</p>
        </section>

        <section class="tarjeta">
          <h2><ion-icon name="eye-off-outline" />Privado por defecto</h2>
          <p>Tus observaciones son privadas. Tú decides si publicas cada una (o todas, desde tu perfil). Los avistamientos públicos
            muestran tu nombre de usuario, nunca tu correo.</p>
        </section>

        <section class="tarjeta">
          <h2><ion-icon name="sparkles-outline" />Inteligencia artificial y servicios externos</h2>
          <p>Para identificar la especie, la foto se envía a Claude (de Anthropic). Los nombres científicos se comprueban en GBIF y las
            fotos de referencia vienen de Wikimedia Commons e iNaturalist, con licencias libres. La IA puede equivocarse: confirma con
            un experto antes de tocar o consumir cualquier animal o planta.</p>
        </section>

        <section class="tarjeta">
          <h2><ion-icon name="person-outline" />Tu cuenta y tus derechos</h2>
          <p>Guardamos tu correo, tu nombre de usuario y tus observaciones. Puedes cambiar tu nombre o eliminar tu cuenta cuando quieras
            desde tu perfil: se borran tu cuenta, tus fotos y tus observaciones. Si usas la app sin cuenta, tus datos quedan ligados a este
            dispositivo hasta que crees tu cuenta o cierres sesión.</p>
        </section>

        <section class="tarjeta">
          <h2><ion-icon name="shield-checkmark-outline" />Uso justo</h2>
          <p>Cada persona tiene un número de identificaciones al día para que el servicio siga siendo gratuito. No subas fotos de otras
            personas sin su permiso ni contenido que no sea de animales o plantas. Las especies protegidas por la NOM-059-SEMARNAT
            deben observarse sin molestarlas.</p>
        </section>
      </div>
    </ion-content>
  `,
  styles: `
    .tarjeta { display: flex; flex-direction: column; gap: 8px; }
    h2 { margin: 0; font-size: 18px; display: flex; align-items: center; gap: 8px; }
    h2 ion-icon { color: var(--c-primario); font-size: 22px; flex: none; }
    p { margin: 0; font-size: 15px; line-height: 1.6; color: var(--c-texto-2); }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PrivacidadPage {
  private readonly nav = inject(NavController);

  volver(): void {
    this.nav.back();
  }
}
