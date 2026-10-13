import { fechaCorta, seccionHistorial, tiempoHasta } from './fechas';

describe('fechas', () => {
  const ahora = new Date(2026, 9, 12, 15, 0); // 12 oct 2026, 15:00

  it('fecha corta', () => {
    expect(fechaCorta(new Date(2026, 9, 12, 9).toISOString(), ahora)).toBe('Hoy');
    expect(fechaCorta(new Date(2026, 9, 11, 22).toISOString(), ahora)).toBe('Ayer');
    expect(fechaCorta(new Date(2026, 9, 5).toISOString(), ahora)).toBe('5 oct');
    expect(fechaCorta(new Date(2025, 0, 3).toISOString(), ahora)).toBe('3 ene 2025');
  });

  it('secciones del historial', () => {
    expect(seccionHistorial(new Date(2026, 9, 10).toISOString(), ahora)).toBe('Esta semana');
    expect(seccionHistorial(new Date(2026, 8, 20).toISOString(), ahora)).toBe('Septiembre');
  });

  it('tiempo restante', () => {
    expect(tiempoHasta(new Date(ahora.getTime() + (3 * 60 + 20) * 60000).toISOString(), ahora)).toBe('3 h 20 min');
    expect(tiempoHasta(new Date(ahora.getTime() + 45 * 60000).toISOString(), ahora)).toBe('45 min');
    expect(tiempoHasta(new Date(ahora.getTime() - 60000).toISOString(), ahora)).toBe('0 min');
  });
});
