import {
  GRUPOS, colorGrupo, estiloGrupo, etiquetaConservacion, iconoEspecie, nivelConfianza, nombreEstado, nombreGrupo, porcentaje, reinoDeGrupo,
} from './grupos';

describe('grupos', () => {
  it('clasifica plantas por reino y animales por grupo', () => {
    const plantas = GRUPOS.find((g) => g.id === 'planta')!;
    const aves = GRUPOS.find((g) => g.id === 'ave')!;
    expect(plantas.incluye({ reino: 'planta', grupo: 'cactacea' })).toBe(true);
    expect(aves.incluye({ reino: 'animal', grupo: 'ave' })).toBe(true);
    expect(aves.incluye({ reino: 'animal', grupo: 'mamifero' })).toBe(false);
  });

  it('nombres y etiquetas', () => {
    expect(nombreGrupo('cactacea')).toBe('Cactácea');
    expect(nombreGrupo('otro')).toBe('Otro');
    expect(etiquetaConservacion({ categoria_nom059: 'P', introducida: false })).toBe('En peligro');
    expect(etiquetaConservacion({ categoria_nom059: null, introducida: true })).toBe('Introducida');
    expect(etiquetaConservacion({ categoria_nom059: null, introducida: false })).toBeNull();
    expect(nombreEstado('elegida')).toBe('Elegida por ti');
  });

  it('confianza legible', () => {
    expect(porcentaje(0.94)).toBe('94 %');
    expect(nivelConfianza(0.94)).toBe('Muy alta');
    expect(nivelConfianza(0.75)).toBe('Alta');
    expect(nivelConfianza(0.48)).toBe('Baja');
  });

  it('colores e iconos por grupo', () => {
    expect(colorGrupo({ reino: 'planta', grupo: 'arbol' })).toBe('planta');
    expect(colorGrupo({ reino: 'animal', grupo: 'invertebrado' })).toBe('invertebrado');
    expect(estiloGrupo({ reino: 'animal', grupo: 'ave' })).toEqual({ '--grupo': 'var(--g-ave)', '--grupo-suave': 'var(--g-ave-suave)' });
    expect(iconoEspecie({ reino: 'animal', grupo: 'invertebrado' })).toBe('grupo-insecto');
    expect(reinoDeGrupo('cactacea')).toBe('planta');
    expect(reinoDeGrupo('pez')).toBe('animal');
    expect(reinoDeGrupo(null)).toBe('animal');
  });
});
