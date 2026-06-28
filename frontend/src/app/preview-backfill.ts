import { SourceCard } from './models';
import { SourcesService } from './sources.service';

/**
 * Lazily fill missing preview images for node-less sources (YouTube, Bayerischer Rundfunk, bare
 * Bezugsquellen) from one representative live content. Shared by the tile and list views so the
 * logic lives in one place.
 *
 * Mutates `into` (keyed by source id) as each lookup resolves; the surrounding zone change
 * detection re-renders the card once a url lands. Cards that already have a previewUrl, or one
 * already resolved, are skipped. The service caches each lookup, so the only cost is one cheap
 * request per node-less source per session — bounded by the page size, since only rendered cards
 * are passed in.
 */
export function backfillPreviews(
  items: SourceCard[],
  api: SourcesService,
  into: Map<string, string>,
): void {
  for (const s of items) {
    if (s.previewUrl || into.has(s.id)) continue;
    into.set(s.id, ''); // mark in-flight so re-renders don't re-subscribe
    api.cardPreview(s.id).subscribe((url) => {
      if (url) into.set(s.id, url);
    });
  }
}
