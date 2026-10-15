/** Estilos compartidos de las pantallas de acceso (entrar, registro, recuperar y nueva contraseña). */
export const ESTILOS_ACCESO = `
  .cabecera {
    position: relative; padding: calc(20px + env(safe-area-inset-top)) 22px 70px; color: #fff;
    background: radial-gradient(110% 80% at 100% 0%, rgba(227, 155, 45, .3) 0%, transparent 55%), linear-gradient(160deg, #1f6b4f, #12452f);
    border-radius: 0 0 var(--radio-xl) var(--radio-xl); display: flex; flex-direction: column; gap: 18px;
  }
  .arriba { display: flex; justify-content: space-between; align-items: center; }
  .volver { width: 42px; height: 42px; border-radius: 50%; border: 0; background: rgba(255, 255, 255, .16); color: #fff; font-size: 22px; display: flex; align-items: center; justify-content: center; text-decoration: none; }
  .cabecera h1 { margin: 6px 0 0; font-size: 29px; color: #fff; }
  .cabecera p { margin: 0; color: rgba(255, 255, 255, .82); font-size: 15.5px; line-height: 1.5; }
  form, .tarjeta-acceso {
    margin: -44px 16px 0; position: relative; background: var(--c-superficie); border-radius: var(--radio-l); padding: 22px 18px;
    display: flex; flex-direction: column; gap: 14px; box-shadow: var(--sombra-3); border: 1px solid var(--c-borde);
  }
  .clave { position: relative; }
  .clave input { padding-right: 48px; }
  .ver { position: absolute; right: 6px; bottom: 6px; width: 40px; height: 40px; border: 0; background: transparent; color: var(--c-texto-3); font-size: 20px; display: flex; align-items: center; justify-content: center; }
  .boton ion-spinner { width: 20px; height: 20px; color: inherit; }
  .enlaces { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 24px 22px 32px; font-size: 14.5px; color: var(--c-texto-2); }
  .enlaces a { color: var(--c-primario-texto); font-weight: 750; text-decoration: none; }
  .separador { display: flex; align-items: center; gap: 12px; color: var(--c-texto-3); font-size: 13px; font-weight: 700; }
  .separador::before, .separador::after { content: ''; flex: 1; height: 1px; background: var(--c-borde); }
`;
