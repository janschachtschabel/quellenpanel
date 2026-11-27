import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { AppComponent } from './app.component';

function erzeuge(attr: Record<string, string>) {
  const f = TestBed.createComponent(AppComponent);
  for (const [k, v] of Object.entries(attr)) f.componentRef.setInput(k, v);
  f.detectChanges();
  return f;
}

describe('schlanke Einbettung (Kopf, Fuß, Filter, Rahmen, Ansicht, Farben)', () => {
  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations()],
    });
    await TestBed.compileComponents();
  });

  it('ohne Attribute: Kopf, Filter und Fuß sind da, Rahmen an', () => {
    const el = erzeuge({}).nativeElement as HTMLElement;
    expect(el.querySelector('header.bar')).not.toBeNull();
    expect(el.querySelector('.filters')).not.toBeNull();
    expect(el.querySelector('footer.appfoot')).not.toBeNull();
    expect(el.querySelector('.host')?.classList.contains('ohne-rahmen')).toBe(false);
  });

  it('kopf/fuss/filter/rahmen="aus" blenden die Teile aus, die Liste bleibt', () => {
    const f = erzeuge({ kopf: 'aus', fuss: 'aus', filter: 'aus', rahmen: 'aus', ansicht: 'liste' });
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('header.bar')).toBeNull();
    expect(el.querySelector('footer.appfoot')).toBeNull();
    expect(el.querySelector('.filters')).toBeNull();
    expect(el.querySelector('.host')?.classList.contains('ohne-rahmen')).toBe(true);
    expect(f.componentInstance.view).toBe('list');
    expect(el.querySelector('wlo-list')).not.toBeNull();
  });

  it('hintergrund und farbe setzen die Tokens am Element (nur gültige #rrggbb)', () => {
    const f = erzeuge({ hintergrund: '#ffffff', farbe: '#1a73e8' });
    const host = f.nativeElement as HTMLElement;
    expect(host.style.getPropertyValue('--backgroundColor')).toBe('#ffffff');
    expect(host.style.getPropertyValue('--primary')).toBe('#1a73e8');
    const g = erzeuge({ hintergrund: 'red;x:y' });
    expect((g.nativeElement as HTMLElement).style.getPropertyValue('--backgroundColor')).toBe('');
  });

  it('die eigene Farbe gewinnt gegen die Markenfarbe aus dem Profil', () => {
    const f = erzeuge({ farbe: '#008080' });
    f.componentInstance.tiers.branding.set({ primary: '#003b7c' });
    f.detectChanges();
    TestBed.tick();
    expect((f.nativeElement as HTMLElement).style.getPropertyValue('--primary')).toBe('#008080');
  });
});
