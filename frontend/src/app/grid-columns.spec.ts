import { describe, it, expect } from 'vitest';
import { columnsFromMatcher, roundToRows, pageSizeOptionsFor } from './grid-columns';

/** A matcher for a fixed viewport width: min-width query matches when the width reaches it. */
const at = (width: number) => (min: number) => width >= min;

describe('columnsFromMatcher', () => {
  it('picks the widest breakpoint whose min-width is met', () => {
    expect(columnsFromMatcher(at(1300))).toBe(5);
    expect(columnsFromMatcher(at(1000))).toBe(4);   // downward-resize case (regression guard: was stuck at 5)
    expect(columnsFromMatcher(at(700))).toBe(3);
    expect(columnsFromMatcher(at(400))).toBe(2);
  });

  it('falls back to the narrowest column count below every breakpoint', () => {
    expect(columnsFromMatcher(() => false)).toBe(2);
  });
});

describe('roundToRows', () => {
  it('rounds a page size up to full rows for the column count', () => {
    expect(roundToRows(24, 5)).toBe(25);
    expect(roundToRows(24, 4)).toBe(24);
    expect(roundToRows(12, 5)).toBe(15);
  });
});

describe('pageSizeOptionsFor', () => {
  it('rounds each base option to full rows, de-duplicated', () => {
    expect(pageSizeOptionsFor(4)).toEqual([12, 24, 48, 96]);
    expect(pageSizeOptionsFor(5)).toEqual([15, 25, 50, 100]);
  });
});
