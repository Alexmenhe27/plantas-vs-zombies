import { GRUPOS, etiquetaConservacion, nivelConfianza, nombreGrupo, porcentaje } from './grupos';

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
  });

  it('confianza legible', () => {
    expect(porcentaje(0.94)).toBe('94 %');
    expect(nivelConfianza(0.94)).toBe('Muy alta');
    expect(nivelConfianza(0.75)).toBe('Alta');
    expect(nivelConfianza(0.48)).toBe('Baja');
  });
});
