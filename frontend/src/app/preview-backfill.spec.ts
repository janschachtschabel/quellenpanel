import { describe, it, expect, vi } from 'vitest';
import { of } from 'rxjs';
import { backfillPreviews } from './preview-backfill';
import { SourcesService } from './sources.service';
import { SourceCard } from './models';

/** Minimal SourceCard for the helper (only id + previewUrl are read). */
function card(id: string, previewUrl = ''): SourceCard {
  return { id, name: id, previewUrl } as SourceCard;
}

/** cardPreview is stubbed with a synchronous observable, so resolution is observable inline. */
describe('backfillPreviews', () => {
  it('skips cards that already have a previewUrl', () => {
    const api = { cardPreview: vi.fn() } as unknown as SourcesService;
    const into = new Map<string, string>();
    backfillPreviews([card('a', 'https://img/a.jpg')], api, into);
    expect(api.cardPreview).not.toHaveBeenCalled();
    expect(into.has('a')).toBe(false);
  });

  it('resolves and stores a preview for node-less cards', () => {
    const api = { cardPreview: vi.fn((id: string) => of('img-' + id)) } as unknown as SourcesService;
    const into = new Map<string, string>();
    backfillPreviews([card('b')], api, into);
    expect(api.cardPreview).toHaveBeenCalledWith('b');
    expect(into.get('b')).toBe('img-b');
  });

  it('keeps the empty in-flight marker when no image exists, so it renders the placeholder and is not re-fetched', () => {
    const api = { cardPreview: vi.fn(() => of('')) } as unknown as SourcesService;
    const into = new Map<string, string>();
    backfillPreviews([card('c')], api, into);
    expect(into.get('c')).toBe('');   // falsy → template shows the placeholder
    expect(into.has('c')).toBe(true); // marked → a later render won't refetch
  });

  it('does not re-fetch ids already present in the map', () => {
    const api = { cardPreview: vi.fn(() => of('x')) } as unknown as SourcesService;
    const into = new Map<string, string>([['d', 'https://img/d.jpg']]);
    backfillPreviews([card('d')], api, into);
    expect(api.cardPreview).not.toHaveBeenCalled();
  });
});
