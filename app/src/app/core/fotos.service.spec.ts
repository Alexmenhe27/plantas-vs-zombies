import { normalizar } from './catalogo.service';
import { motivoSubida, rutaMini } from './fotos.service';

describe('motivoSubida', () => {
  it('explica la causa real en lugar de "sin internet"', () => {
    expect(motivoSubida('new row violates row-level security policy')).toContain('sesión');
    expect(motivoSubida('Bucket not found')).toContain('bucket');
    expect(motivoSubida('The object exceeded the maximum allowed size')).toContain('5 MB');
    expect(motivoSubida('mime type image/heic is not supported')).toContain('formato');
    expect(motivoSubida('algo raro')).toBe('No pudimos guardar tu foto: algo raro');
  });
});

describe('rutas y búsqueda', () => {
  it('la miniatura vive junto a la foto', () => {
    expect(rutaMini('u1/abc.jpg')).toBe('u1/abc.mini.jpg');
  });

  it('la búsqueda ignora acentos y mayúsculas (igual que la base de datos)', () => {
    expect(normalizar('Búho CORNUDO')).toBe('buho cornudo');
    expect(normalizar('Ñandú')).toBe('nandu');
  });
});
