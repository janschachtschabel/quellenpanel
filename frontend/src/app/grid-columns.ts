/**
 * Responsive tile-grid column model: how many columns are shown at a given viewport, and how a
 * page size is rounded to whole rows for that column count. Kept pure and framework-free so it can
 * be unit-tested directly; the app component owns only the matchMedia wiring that drives it.
 */

export interface Breakpoint {
  min: number;   // min viewport width (px) at which `cols` applies
  cols: number;
}

/**
 * Column breakpoints, WIDEST FIRST — the first breakpoint whose min-width is met wins. Mirrors the
 * CSS grid breakpoints in tiles.component (2 → 3 → 4 → 5 columns).
 */
export const COL_BREAKPOINTS: Breakpoint[] = [
  { min: 1240, cols: 5 },
  { min: 921, cols: 4 },
  { min: 621, cols: 3 },
  { min: 0, cols: 2 },
];

/**
 * Column count for the current viewport, chosen via a `matches(minPx)` predicate (typically backed
 * by window.matchMedia). Returns the first breakpoint (widest first) whose min-width is met — which
 * is correct whether the viewport grew OR shrank across a breakpoint. Falls back to the last
 * (narrowest) breakpoint's column count.
 */
export function columnsFromMatcher(matches: (minPx: number) => boolean,
                                   breakpoints: Breakpoint[] = COL_BREAKPOINTS): number {
  for (const bp of breakpoints) {
    if (matches(bp.min)) return bp.cols;
  }
  return breakpoints[breakpoints.length - 1].cols;
}

/** Round a page size UP to a whole number of rows for the given column count. */
export function roundToRows(pageSize: number, cols: number): number {
  return Math.ceil(pageSize / cols) * cols;
}

/** Distinct page-size options (from the base sizes) rounded to whole rows for the column count. */
export function pageSizeOptionsFor(cols: number, bases: number[] = [12, 24, 48, 96]): number[] {
  return [...new Set(bases.map((n) => roundToRows(n, cols)))];
}
