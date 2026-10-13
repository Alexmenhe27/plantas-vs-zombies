import { TestBed } from '@angular/core/testing';
import { ApiService, ErrorIdentificacion, aError } from './api.service';
import { SupabaseService } from './supabase.service';

describe('ApiService', () => {
  let api: ApiService;
  const peticion = { ruta_foto: 'u/1.jpg', latitud: 19.04, longitud: -98.2, observada_en: '2026-10-12T10:00:00Z' };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [{ provide: SupabaseService, useValue: { token: () => 'jwt-de-prueba' } }],
    });
    api = TestBed.inject(ApiService);
  });

  it('envía la foto con el token y devuelve la observación', async () => {
    let recibido: RequestInit | undefined;
    const falso = (async (_url: string, init?: RequestInit) => {
      recibido = init;
      return new Response(JSON.stringify({ observacion: { id: 'o1' }, restantes: 9 }), { status: 200 });
    }) as unknown as typeof fetch;
    const r = await api.identificar(peticion, falso);
    expect(r.restantes).toBe(9);
    expect((recibido!.headers as Record<string, string>)['Authorization']).toBe('Bearer jwt-de-prueba');
    expect(JSON.parse(recibido!.body as string).ruta_foto).toBe('u/1.jpg');
  });

  it('sin internet devuelve sin_conexion', async () => {
    const falso = (async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await expect(api.identificar(peticion, falso)).rejects.toMatchObject({ codigo: 'sin_conexion' });
    vi.restoreAllMocks();
  });

  it('con internet pero sin respuesta de la API dice que el servidor no está disponible (no "sin internet")', async () => {
    const falso = (async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch;
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    await expect(api.identificar(peticion, falso)).rejects.toMatchObject({ codigo: 'servidor_inaccesible' });
    vi.restoreAllMocks();
  });

  it('traduce el límite diario con la hora disponible', async () => {
    const falso = (async () =>
      new Response(JSON.stringify({ detail: { codigo: 'limite_diario', mensaje: 'x', disponible_en: '2026-10-12T18:00:00Z' } }), {
        status: 429,
      })) as unknown as typeof fetch;
    const error = (await api.identificar(peticion, falso).catch((e) => e)) as ErrorIdentificacion;
    expect(error.codigo).toBe('limite_diario');
    expect(error.disponibleEn).toBe('2026-10-12T18:00:00Z');
  });

  it('errores desconocidos', () => {
    expect(aError(500, 'html').codigo).toBe('desconocido');
    expect(aError(401, {}).codigo).toBe('sin_sesion');
    expect(aError(502, { detail: { codigo: 'ia_no_disponible', mensaje: 'Gemini tardó' } }).codigo).toBe('ia_no_disponible');
    expect(aError(500, { detail: { codigo: 'error_interno', mensaje: 'Ocurrió un error en el servidor.' } }).message).toBe(
      'Ocurrió un error en el servidor.',
    );
  });
});
