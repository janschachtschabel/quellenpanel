/**
 * Default backend for the embedded element bundle: the origin the bundle was loaded from + /api.
 * Without it, a heavy element inserted after the bundle is defined would initialise before anyone
 * set api-base and talk to the HOST page's /api (with the host's cookies).
 */
export function elementApiBase(moduleUrl: string): string {
  try { return new URL('/api', moduleUrl).href; } catch { return ''; }
}

/** Subclass of an element constructor that sets a missing api-base before it connects. */
export function mitStandardApi(ctor: CustomElementConstructor, base: string): CustomElementConstructor {
  return class extends (ctor as unknown as typeof HTMLElement) {
    connectedCallback(): void {
      if (base && !this.hasAttribute('api-base')) this.setAttribute('api-base', base);
      (ctor.prototype as { connectedCallback?: () => void }).connectedCallback?.call(this);
    }
  } as unknown as CustomElementConstructor;
}
