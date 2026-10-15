import { TestBed } from '@angular/core/testing';
import { ApiService, ErrorIdentificacion, aError } from './api.service';
import { leerNdjson } from './lector-ndjson';
import { EventoIdentificacion } from './modelos';
import { SupabaseService } from './supabase.service';

/** Respuesta que llega en trozos (como el streaming real), cortando líneas y letras con acento a la mitad. */
function respuestaEnTrozos(texto: string, tamano = 7, tipo = 'application/x-ndjson'): Response {
  const bytes = new TextEncoder().encode(texto);
  const cuerpo = new ReadableStream<Uint8Array>({
    start(c) {
      for (let i = 0; i < bytes.length; i += tamano) c.enqueue(bytes.slice(i, i + tamano));
      c.close();
    },
  });
  return new Response(cuerpo, { status: 200, headers: { 'content-type': tipo } });
}

const OBS = { id: 'o1', estado: 'identificada', especie: { id: 1, nombre_comun: 'Búho cornudo' } };
const NDJSON = [
  { tipo: 'parcial', problema: 'ninguno' },
  { tipo: 'parcial', problema: 'ninguno', nombre_comun: 'Búho cornudo', nombre_cientifico: 'Bubo virginianus' },
  { tipo: 'resultado', observacion: OBS, restantes: 9, limite: 10, candidatos_especies: [], ficha_pendiente: true },
  { tipo: 'ficha', especie: { id: 1, nombre_comun: 'Búho cornudo', descripcion: 'Gran búho con "orejas".' } },
  { tipo: 'fin', tiempos: { total: 4100 } },
].map((e) => JSON.stringify(e)).join('\n') + '\n';

describe('ApiService', () => {
  let api: ApiService;
  const peticion = { ruta_foto: 'u/1.jpg', latitud: 19.04, longitud: -98.2, observada_en: '2026-10-12T10:00:00Z' };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [{ provide: SupabaseService, useValue: { token: () => 'jwt-de-prueba' } }],
    });
    api = TestBed.inject(ApiService);
  });

  it('pide la respuesta por partes y avisa cada evento en orden', async () => {
    let recibido: RequestInit | undefined;
    const falso = (async (_url: string, init?: RequestInit) => {
      recibido = init;
      return respuestaEnTrozos(NDJSON);
    }) as unknown as typeof fetch;
    const eventos: EventoIdentificacion[] = [];
    const r = await api.identificar(peticion, (e) => eventos.push(e), falso);

    expect(r.restantes).toBe(9);
    expect(r.observacion.id).toBe('o1');
    expect(eventos.map((e) => e.tipo)).toEqual(['parcial', 'parcial', 'resultado', 'ficha', 'fin']);
    expect((eventos[1] as { nombre_comun: string }).nombre_comun).toBe('Búho cornudo');
    const cabeceras = recibido!.headers as Record<string, string>;
    expect(cabeceras['Authorization']).toBe('Bearer jwt-de-prueba');
    expect(cabeceras['Accept']).toBe('application/x-ndjson');
    expect(JSON.parse(recibido!.body as string).ruta_foto).toBe('u/1.jpg');
  });

  it('también entiende la respuesta de un solo JSON (versión anterior de la API)', async () => {
    const falso = (async () =>
      new Response(JSON.stringify({ observacion: OBS, restantes: 4, limite: 10, candidatos_especies: [], ficha_pendiente: false }), {
        status: 200, headers: { 'content-type': 'application/json' },
      })) as unknown as typeof fetch;
    const eventos: EventoIdentificacion[] = [];
    const r = await api.identificar(peticion, (e) => eventos.push(e), falso);
    expect(r.restantes).toBe(4);
    expect(eventos.map((e) => e.tipo)).toEqual(['resultado']);
  });

  it('un error de la IA a medio camino se vuelve ErrorIdentificacion', async () => {
    const texto = JSON.stringify({ tipo: 'parcial', problema: 'ninguno' }) + '\n'
      + JSON.stringify({ tipo: 'error', codigo: 'ia_no_disponible', mensaje: 'Claude está saturado.' }) + '\n';
    const falso = (async () => respuestaEnTrozos(texto)) as unknown as typeof fetch;
    const error = (await api.identificar(peticion, () => undefined, falso).catch((e) => e)) as ErrorIdentificacion;
    expect(error.codigo).toBe('ia_no_disponible');
    expect(error.message).toBe('Claude está saturado.');
  });

  it('si la conexión se corta después del resultado, el resultado vale', async () => {
    const resultado = JSON.stringify({ tipo: 'resultado', observacion: OBS, restantes: 3, limite: 10, candidatos_especies: [] }) + '\n';
    let paso = 0;
    const cuerpo = new ReadableStream<Uint8Array>({
      pull(c) {
        if (paso++ === 0) c.enqueue(new TextEncoder().encode(resultado));
        else c.error(new TypeError('network error'));
      },
    });
    const falso = (async () => new Response(cuerpo, { headers: { 'content-type': 'application/x-ndjson' } })) as unknown as typeof fetch;
    const r = await api.identificar(peticion, () => undefined, falso);
    expect(r.restantes).toBe(3);
  });

  it('sin internet devuelve sin_conexion', async () => {
    const falso = (async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await expect(api.identificar(peticion, () => undefined, falso)).rejects.toMatchObject({ codigo: 'sin_conexion' });
    vi.restoreAllMocks();
  });

  it('con internet pero sin respuesta de la API dice que el servidor no está disponible (no "sin internet")', async () => {
    const falso = (async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    await expect(api.identificar(peticion, () => undefined, falso)).rejects.toMatchObject({ codigo: 'servidor_inaccesible' });
    vi.restoreAllMocks();
  });

  it('traduce el límite diario con la hora disponible y si es invitado', async () => {
    const falso = (async () =>
      new Response(JSON.stringify({ detail: { codigo: 'limite_diario', mensaje: 'x', disponible_en: '2026-10-12T18:00:00Z', invitado: true } }), {
        status: 429,
      })) as unknown as typeof fetch;
    const error = (await api.identificar(peticion, () => undefined, falso).catch((e) => e)) as ErrorIdentificacion;
    expect(error.codigo).toBe('limite_diario');
    expect(error.disponibleEn).toBe('2026-10-12T18:00:00Z');
    expect(error.invitado).toBe(true);
  });

  it('elegir entre las parecidas', async () => {
    const llamadas: [string, RequestInit][] = [];
    const falso = (async (url: string, init: RequestInit) => {
      llamadas.push([url, init]);
      return new Response(JSON.stringify({ observacion: { id: 'o 1', estado: 'elegida' } }));
    }) as unknown as typeof fetch;
    const o = await api.elegir('o 1', 'Romerolagus diazi', falso);
    expect(o.estado).toBe('elegida');
    expect(llamadas[0][0]).toContain('/observaciones/o%201/elegir');
    expect(JSON.parse(llamadas[0][1].body as string)).toEqual({ nombre_cientifico: 'Romerolagus diazi' });
  });

  it('errores desconocidos', () => {
    expect(aError(500, 'html').codigo).toBe('desconocido');
    expect(aError(401, {}).codigo).toBe('sin_sesion');
    expect(aError(502, { detail: { codigo: 'ia_no_disponible', mensaje: 'Claude tardó' } }).codigo).toBe('ia_no_disponible');
    expect(aError(503, { detail: { codigo: 'servicio_saturado', mensaje: 'Muchas' } }).codigo).toBe('servicio_saturado');
    expect(aError(500, { detail: { codigo: 'error_interno', mensaje: 'Ocurrió un error en el servidor.' } }).message).toBe(
      'Ocurrió un error en el servidor.',
    );
  });
});

describe('leerNdjson', () => {
  it('arma cada objeto aunque las líneas y los acentos lleguen partidos', async () => {
    const objetos: unknown[] = [];
    await leerNdjson(respuestaEnTrozos('{"a":"Búho"}\n\n{"b":"ñandú"}\n{"c":3}', 3).body!, (o) => objetos.push(o));
    expect(objetos).toEqual([{ a: 'Búho' }, { b: 'ñandú' }, { c: 3 }]);
  });
});
