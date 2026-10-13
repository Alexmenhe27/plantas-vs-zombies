/** Estilos compartidos de las pantallas de acceso (diseño V1 · Iniciar sesión). */
export const ESTILOS_ACCESO = `
  .cabecera { background: var(--pvz-verde); color: #fff; padding: 48px 24px 64px; border-radius: 0 0 28px 28px; }
  .marca { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 15px; color: #cfe3d8; }
  .marca ion-icon { font-size: 28px; color: var(--pvz-ambar); }
  .cabecera h1 { margin: 18px 0 6px; font-size: 26px; line-height: 1.2; }
  .cabecera p { margin: 0; color: #cfe3d8; font-size: 15px; line-height: 1.5; }
  form { margin: -36px 18px 0; background: #fff; border-radius: 22px; padding: 20px 18px; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 10px 28px rgba(14,77,58,.12); }
  label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 700; color: var(--pvz-texto-suave); }
  input { height: 50px; border-radius: 14px; border: 1.5px solid var(--pvz-borde-fuerte); padding: 0 14px; font: inherit; font-size: 16px; color: var(--pvz-texto); background: #f8faf8; }
  input:focus { outline: 2px solid var(--pvz-verde); border-color: transparent; }
  .error { margin: 0; padding: 10px 12px; border-radius: 12px; background: var(--pvz-rojo-claro); color: var(--pvz-rojo-texto); font-size: 14px; font-weight: 600; }
  .ok { margin: 0; padding: 10px 12px; border-radius: 12px; background: var(--pvz-verde-claro); color: var(--pvz-verde-texto); font-size: 14px; font-weight: 600; }
  .enlaces { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 22px; font-size: 14px; }
  a { color: var(--pvz-verde); font-weight: 700; text-decoration: none; }
`;
