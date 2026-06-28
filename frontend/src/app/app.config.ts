import { ApplicationConfig, LOCALE_ID, provideZoneChangeDetection } from '@angular/core';
import { registerLocaleData } from '@angular/common';
import localeDe from '@angular/common/locales/de';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';

import { credentialsInterceptor } from './credentials.interceptor';

registerLocaleData(localeDe);

export const appConfig: ApplicationConfig = {
  providers: [
    // Explicit zone change detection. Without it, async HTTP responses did not trigger a render
    // under Angular 21 — the view stayed frozen on "0 Quellen"/loading even though data arrived.
    // eventCoalescing additionally collapses redundant change-detection cycles.
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideHttpClient(withInterceptors([credentialsInterceptor])),
    provideAnimationsAsync(),
    { provide: LOCALE_ID, useValue: 'de-DE' },   // German number formatting (62.867 not 62,867)
  ],
};
