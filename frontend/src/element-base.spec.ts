import { describe, it, expect } from 'vitest';
import { elementApiBase, mitStandardApi } from './element-base';

describe('element bundle default api-base (review finding)', () => {
  it('derives /api from the bundle location', () => {
    expect(elementApiBase('https://q.example/widgets/element/main.js')).toBe('https://q.example/api');
    expect(elementApiBase('nicht-url')).toBe('');
  });

  it('sets api-base before connecting, also for elements inserted after definition', () => {
    const gesehen: (string | null)[] = [];
    class Basis extends HTMLElement {
      connectedCallback(): void { gesehen.push(this.getAttribute('api-base')); }
    }
    customElements.define('x-basis-test', mitStandardApi(Basis, 'https://q.example/api'));
    const a = document.createElement('x-basis-test');
    document.body.append(a);
    const b = document.createElement('x-basis-test');
    b.setAttribute('api-base', 'https://andere/api');
    document.body.append(b);
    expect(gesehen).toEqual(['https://q.example/api', 'https://andere/api']);
    a.remove(); b.remove();
  });
});
