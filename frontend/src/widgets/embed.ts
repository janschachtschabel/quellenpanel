/**
 * embed.js — runs inside the /embed/<name> iframe page. Reports the content height to the parent
 * ONLY after the parent asked ({type: "quellenpanel:hoehe?"}), to that window and origin, and then
 * again whenever the height changes. Other messages are ignored.
 */
export function hoeheAntworten(ev: MessageEvent, hoehe: number): boolean {
  const d = ev.data as { type?: unknown } | null;
  if (!d || typeof d !== 'object' || d.type !== 'quellenpanel:hoehe?' || !ev.source) return false;
  (ev.source as Window).postMessage({ type: 'quellenpanel:hoehe', hoehe }, ev.origin || '*');
  return true;
}

export function starteEmbed(): void {
  let ziel: { source: Window; origin: string } | null = null;
  const hoehe = () => Math.ceil(document.documentElement.scrollHeight);
  window.addEventListener('message', (ev) => {
    if (hoeheAntworten(ev, hoehe())) ziel = { source: ev.source as Window, origin: ev.origin || '*' };
  });
  if (typeof ResizeObserver !== 'undefined') {
    let letzte = 0;
    new ResizeObserver(() => {
      const h = hoehe();
      if (ziel && h !== letzte) { letzte = h; ziel.source.postMessage({ type: 'quellenpanel:hoehe', hoehe: h }, ziel.origin); }
    }).observe(document.body);
  }
}
