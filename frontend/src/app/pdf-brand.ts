/**
 * Shared PDF branding + text helpers used by both PDF products (the multi-source Steckbrief and the
 * list table). Pure and dependency-light so the document builders stay testable.
 */

/** autotable's functional entry point, resolved from the lazy import. */
export type AutoTable = typeof import('jspdf-autotable')['default'];

// WissenLebtOnline brand palette (RGB).
export const NAVY: [number, number, number] = [0, 59, 124];
export const MUTED: [number, number, number] = [91, 107, 134];
export const TEXT: [number, number, number] = [40, 50, 70];
// Top brand bar: blue → light blue → slate → lime → pink.
export const BAR: Array<[number, number, number]> = [
  [0, 59, 124], [46, 108, 168], [123, 160, 201], [163, 206, 60], [236, 74, 112],
];
export const M = 14; // page margin (mm)

export const num = (n: number): string => (n || 0).toLocaleString('de-DE');
export const arr = (x: unknown): string => (Array.isArray(x) ? x.join(', ') : String(x ?? ''));

/** Collapse whitespace and cap length (… ellipsis) — keeps table cells from overflowing. */
export const clip = (v: unknown, n: number): string => {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n) + '…' : s;
};

/** Legal/AI fields can be huge (a whole robots.txt). Truncate long ones, drop the very long. */
export const clipLong = (v: unknown): string => {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (s.length > 400) return '';
  return s.length > 200 ? s.slice(0, 200) + '…' : s;
};

/** Only http(s) URLs become clickable links in the PDF — never javascript:/data:/file: etc., even
 * if a record carried a malformed value. Returns the safe URL, or '' so the caller skips the link. */
export const httpUrl = (u: unknown): string => {
  const s = String(u ?? '').trim();
  return /^https?:\/\//i.test(s) ? s : '';
};
