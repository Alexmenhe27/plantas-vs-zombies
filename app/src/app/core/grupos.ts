import { Especie, EstadoObservacion } from './modelos';

/** Grupos de la app, en el orden del diseño (6 grupos de animales + plantas). */
export interface Grupo {
  id: string;
  nombre: string;
  icono: string;
  /** Valores de especies.grupo que entran en este grupo. */
  incluye: (e: Pick<Especie, 'reino' | 'grupo'>) => boolean;
}

export const GRUPOS: Grupo[] = [
  { id: 'ave', nombre: 'Aves', icono: 'grupo-ave', incluye: (e) => e.grupo === 'ave' },
  { id: 'mamifero', nombre: 'Mamíferos', icono: 'grupo-mamifero', incluye: (e) => e.grupo === 'mamifero' },
  { id: 'reptil', nombre: 'Reptiles', icono: 'grupo-reptil', incluye: (e) => e.grupo === 'reptil' },
  { id: 'anfibio', nombre: 'Anfibios', icono: 'grupo-anfibio', incluye: (e) => e.grupo === 'anfibio' },
  { id: 'insecto', nombre: 'Insectos', icono: 'grupo-insecto', incluye: (e) => e.grupo === 'insecto' },
  { id: 'pez', nombre: 'Peces', icono: 'grupo-pez', incluye: (e) => e.grupo === 'pez' },
  { id: 'planta', nombre: 'Plantas', icono: 'grupo-planta', incluye: (e) => e.reino === 'planta' },
];

const NOMBRE_GRUPO: Record<string, string> = {
  ave: 'Ave', mamifero: 'Mamífero', reptil: 'Reptil', anfibio: 'Anfibio', insecto: 'Insecto', pez: 'Pez',
  invertebrado: 'Invertebrado',
  arbol: 'Árbol', arbusto: 'Arbusto', cactacea: 'Cactácea', agave: 'Agave', flor: 'Flor', palma: 'Palma', helecho: 'Helecho', planta: 'Planta',
};

const ICONOS_ANIMAL = new Set(['ave', 'mamifero', 'reptil', 'anfibio', 'insecto', 'pez']);

/** Icono de la especie: el de su grupo; las plantas usan la hoja y otros animales (arañas, caracoles…) el de insecto. */
export function iconoEspecie(e: Pick<Especie, 'reino' | 'grupo'>): string {
  if (e.reino === 'planta') return 'grupo-planta';
  return ICONOS_ANIMAL.has(e.grupo) ? `grupo-${e.grupo}` : 'grupo-insecto';
}

/** Color del grupo (variables --g-* del sistema de diseño). */
export function colorGrupo(e: Pick<Especie, 'reino' | 'grupo'> | null | undefined): string {
  if (!e) return 'planta';
  if (e.reino === 'planta') return 'planta';
  return ICONOS_ANIMAL.has(e.grupo) ? e.grupo : 'invertebrado';
}

/** Estilo para pintar algo con el color del grupo: [style]="estiloGrupo(e)". */
export function estiloGrupo(e: Pick<Especie, 'reino' | 'grupo'> | null | undefined): Record<string, string> {
  const c = colorGrupo(e);
  return { '--grupo': `var(--g-${c})`, '--grupo-suave': `var(--g-${c}-suave)` };
}

export function nombreGrupo(grupo: string): string {
  return NOMBRE_GRUPO[grupo] ?? grupo.charAt(0).toUpperCase() + grupo.slice(1);
}

const NOM059: Record<string, string> = {
  P: 'En peligro',
  A: 'Amenazada',
  Pr: 'Protección especial',
  E: 'Probablemente extinta',
};

export function etiquetaConservacion(e: Pick<Especie, 'categoria_nom059' | 'introducida'>): string | null {
  if (e.categoria_nom059) return NOM059[e.categoria_nom059];
  if (e.introducida) return 'Introducida';
  return null;
}

export function nivelConfianza(c: number | null | undefined): string {
  if (c == null) return '';
  if (c >= 0.9) return 'Muy alta';
  if (c >= 0.7) return 'Alta';
  if (c >= 0.5) return 'Media';
  return 'Baja';
}

export function porcentaje(c: number | null | undefined): string {
  return c == null ? '' : `${Math.round(c * 100)} %`;
}

const ESTADOS: Record<EstadoObservacion, string> = {
  identificada: 'Identificada',
  revisar: 'En revisión',
  elegida: 'Elegida por ti',
  corregida: 'Revisada por un experto',
  no_identificada: 'Sin identificar',
};

export function nombreEstado(estado: EstadoObservacion): string {
  return ESTADOS[estado] ?? estado;
}

/** Colores de cada grupo para el mapa (MapLibre no entiende variables CSS): [modo claro, modo oscuro]. */
export const COLOR_GRUPO_MAPA: Record<string, [string, string]> = {
  ave: ['#3a76b3', '#7fb2e6'],
  mamifero: ['#a3653a', '#dca27a'],
  reptil: ['#6b8732', '#a9c46b'],
  anfibio: ['#1d9584', '#5fd0c0'],
  insecto: ['#c9721c', '#f0a75a'],
  pez: ['#2a62a6', '#7aa8e3'],
  planta: ['#3b8a4d', '#7cc58a'],
  invertebrado: ['#8458b8', '#bf9ae8'],
};

const GRUPOS_PLANTA = new Set(['arbol', 'arbusto', 'cactacea', 'agave', 'flor', 'palma', 'helecho', 'planta']);

/** Reino de un grupo de la app (para especies parecidas que todavía no están en el catálogo). */
export function reinoDeGrupo(grupo: string | null | undefined): 'animal' | 'planta' {
  return grupo && GRUPOS_PLANTA.has(grupo) ? 'planta' : 'animal';
}
