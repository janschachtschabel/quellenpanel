import { Injectable, computed, signal } from '@angular/core';

/**
 * Multi-select state for the Details/Audit tiers (tier 1+): the set of source ids the user has ticked for
 * the "Sammel-PDF" (multi-source PDF) export. Shared between the tile/list views (which render the
 * checkboxes) and the selection bar (which acts on them). Plain ids only — the PDF service fetches
 * the full records on demand, so nothing heavy is held here.
 */
@Injectable({ providedIn: 'root' })
export class SelectionService {
  private readonly ids = signal<Set<string>>(new Set());

  /** Currently selected source ids (read-only view). */
  readonly selected = this.ids.asReadonly();
  /** Number of selected sources — drives the selection bar's visibility and label. */
  readonly count = computed(() => this.ids().size);

  has(id: string): boolean {
    return this.ids().has(id);
  }

  toggle(id: string): void {
    const next = new Set(this.ids());
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    this.ids.set(next);
  }

  clear(): void {
    if (this.ids().size) this.ids.set(new Set());
  }
}
