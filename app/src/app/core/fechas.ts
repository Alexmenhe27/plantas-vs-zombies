const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** "Hoy", "Ayer" o "5 oct". */
export function fechaCorta(iso: string, ahora = new Date()): string {
  const d = new Date(iso);
  const dia = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((dia(ahora) - dia(d)) / 86400000);
  if (diff === 0) return 'Hoy';
  if (diff === 1) return 'Ayer';
  const base = `${d.getDate()} ${MESES[d.getMonth()]}`;
  return d.getFullYear() === ahora.getFullYear() ? base : `${base} ${d.getFullYear()}`;
}

/** "Esta semana", "Septiembre 2026"… para agrupar el historial. */
export function seccionHistorial(iso: string, ahora = new Date()): string {
  const d = new Date(iso);
  const dias = (ahora.getTime() - d.getTime()) / 86400000;
  if (dias < 7) return 'Esta semana';
  const mes = d.toLocaleDateString('es-MX', { month: 'long' });
  const nombre = mes.charAt(0).toUpperCase() + mes.slice(1);
  return d.getFullYear() === ahora.getFullYear() ? nombre : `${nombre} ${d.getFullYear()}`;
}

/** "3 h 20 min" hasta una fecha. */
export function tiempoHasta(iso: string, ahora = new Date()): string {
  const min = Math.max(0, Math.ceil((new Date(iso).getTime() - ahora.getTime()) / 60000));
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h === 0) return `${m} min`;
  return m ? `${h} h ${m} min` : `${h} h`;
}
