import { HttpErrorResponse } from '@angular/common/http';

/** Message of an API error in the service's error shape ({error, message, …}). */
export function fehlertext(e: unknown): string {
  const err = e as HttpErrorResponse;
  return (err?.error && typeof err.error === 'object' && err.error.message) || err?.message || String(e);
}
