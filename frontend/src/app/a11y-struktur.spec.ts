import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';

import { ListComponent } from './list.component';
import { TilesComponent } from './tiles.component';
import { SourceCard } from './models';

const KARTE: SourceCard = {
  id: 'crawler:x', name: 'Serlo', contentCount: 5, url: 'https://serlo.org', searchUrl: '', bezugsquelle: '',
  description: '', subjects: [], educationalContext: [], contentTypes: [], license: '', oer: false, language: '',
  previewUrl: 'https://serlo.org/p.png', erschliessungsstatus: '', quality: {},
};

describe('keyboard and screen-reader structure (review findings Etappe 6)', () => {
  beforeEach(() => TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations()],
  }));

  it('list: each source opens via a real button', () => {
    const f = TestBed.createComponent(ListComponent);
    f.componentInstance.items = [KARTE];
    f.detectChanges();
    const btn = f.nativeElement.querySelector('button.lname') as HTMLButtonElement;
    expect(btn?.textContent).toContain('Serlo');
    let geoeffnet = '';
    f.componentInstance.open.subscribe((id: string) => (geoeffnet += id));
    btn.click();
    expect(geoeffnet).toBe('crawler:x');
    expect(f.nativeElement.querySelector('img.lavatar')?.getAttribute('alt')).toBe('');
  });

  it('tiles: the title is a heading that contains the open button', () => {
    const f = TestBed.createComponent(TilesComponent);
    f.componentInstance.items = [KARTE];
    f.detectChanges();
    const h = f.nativeElement.querySelector('h3') as HTMLElement;
    expect(h).not.toBeNull();
    expect(h.querySelector('button.open')).not.toBeNull();
  });
});
