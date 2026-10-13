import { motivoSubida } from './fotos.service';

describe('motivoSubida', () => {
  it('explica la causa real en lugar de "sin internet"', () => {
    expect(motivoSubida('new row violates row-level security policy')).toContain('sesión');
    expect(motivoSubida('Bucket not found')).toContain('bucket');
    expect(motivoSubida('The object exceeded the maximum allowed size')).toContain('5 MB');
    expect(motivoSubida('mime type image/heic is not supported')).toContain('formato');
    expect(motivoSubida('algo raro')).toBe('No pudimos guardar tu foto: algo raro');
  });
});
