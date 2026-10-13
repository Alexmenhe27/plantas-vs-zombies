import { Especie } from './modelos';

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
