import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { SourcesService } from './sources.service';

/**
 * When the panel is configured for cross-origin team login (the `with-credentials` custom-element
 * attribute / SourcesService.setCredentials), attach `withCredentials: true` to every request so
 * the httpOnly team session cookie is sent and stored across cross-origin calls.
 *
 * Off by default and deliberately so: same-origin requests send the cookie regardless, and a
 * public embed served wildcard CORS (`Access-Control-Allow-Origin: *`) MUST NOT use credentials —
 * the browser would block such a response. Only enable it on an origin the backend trusts via
 * QE_ALLOWED_ORIGINS, which then receives an origin-specific, credentialed CORS grant.
 */
export const credentialsInterceptor: HttpInterceptorFn = (req, next) =>
  inject(SourcesService).useCredentials() ? next(req.clone({ withCredentials: true })) : next(req);
