import { TestBed } from '@angular/core/testing';
import { FotoComponent } from './foto.component';

describe('FotoComponent', () => {
  function crear(src: string | null) {
    const f = TestBed.createComponent(FotoComponent);
    f.componentRef.setInput('src', src);
    f.detectChanges();
    return f;
  }

  it('sin imagen muestra el icono de respaldo', () => {
    const f = crear(null);
    expect(f.nativeElement.querySelector('img')).toBeNull();
    expect(f.nativeElement.querySelector('.respaldo')).not.toBeNull();
  });

  it('al cargar oculta el respaldo; si el enlace falla vuelve al icono', () => {
    const f = crear('https://ejemplo.mx/a.jpg');
    const img: HTMLImageElement = f.nativeElement.querySelector('img');
    img.dispatchEvent(new Event('load'));
    f.detectChanges();
    expect(f.nativeElement.querySelector('.respaldo')).toBeNull();
    expect(img.classList.contains('lista')).toBe(true);

    f.componentRef.setInput('src', 'https://ejemplo.mx/rota.jpg');
    f.detectChanges();
    f.nativeElement.querySelector('img').dispatchEvent(new Event('error'));
    f.detectChanges();
    expect(f.nativeElement.querySelector('img')).toBeNull();
    expect(f.nativeElement.querySelector('.respaldo')).not.toBeNull();
  });
});
