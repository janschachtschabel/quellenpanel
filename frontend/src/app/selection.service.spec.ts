import { describe, it, expect, beforeEach } from 'vitest';
import { SelectionService } from './selection.service';

describe('SelectionService', () => {
  let sel: SelectionService;

  beforeEach(() => {
    sel = new SelectionService();
  });

  it('starts empty', () => {
    expect(sel.count()).toBe(0);
    expect(sel.has('a')).toBe(false);
    expect([...sel.selected()]).toEqual([]);
  });

  it('toggles an id on and off', () => {
    sel.toggle('a');
    expect(sel.has('a')).toBe(true);
    expect(sel.count()).toBe(1);
    sel.toggle('a');
    expect(sel.has('a')).toBe(false);
    expect(sel.count()).toBe(0);
  });

  it('tracks several distinct ids', () => {
    sel.toggle('a');
    sel.toggle('b');
    expect(sel.count()).toBe(2);
    expect([...sel.selected()].sort()).toEqual(['a', 'b']);
  });

  it('clears all selected ids', () => {
    sel.toggle('a');
    sel.toggle('b');
    sel.clear();
    expect(sel.count()).toBe(0);
    expect(sel.has('a')).toBe(false);
  });

  it('emits a fresh Set on change (signal identity changes, no in-place mutation)', () => {
    const before = sel.selected();
    sel.toggle('a');
    const after = sel.selected();
    expect(after).not.toBe(before); // new reference → signal consumers re-render
    expect(before.size).toBe(0);    // the previous snapshot is not mutated
  });
});
