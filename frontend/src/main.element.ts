import { createApplication } from '@angular/platform-browser';
import { createCustomElement } from '@angular/elements';

import { AppComponent } from './app/app.component';
import { appConfig } from './app/app.config';

/**
 * Custom-element entry point. Wraps the same AppComponent the standalone SPA uses as a
 * framework-agnostic <wlo-quellenpanel> element, so any host page can embed the panel with a
 * single tag:
 *
 *   <wlo-quellenpanel api-base="https://backend.example/api"></wlo-quellenpanel>
 *
 * Attributes:
 *   api-base          backend API base when the panel runs on a different origin than the backend.
 *   with-credentials  set to "true" to send the team session cookie cross-origin, enabling team
 *                     login in the embed. Requires the host origin to be listed in the backend's
 *                     QE_ALLOWED_ORIGINS (and HTTPS). Omit for a public, read-only embed.
 *
 * appConfig carries the same providers as the SPA — notably provideZoneChangeDetection, which
 * createApplication() does NOT add implicitly. Without it, async HTTP responses would not render.
 */
createApplication(appConfig)
  .then((appRef) => {
    const element = createCustomElement(AppComponent, { injector: appRef.injector });
    customElements.define('wlo-quellenpanel', element);
  })
  .catch((err) => console.error(err));
