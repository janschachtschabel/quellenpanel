/**
 * embed.js — runs inside the /embed/<name> iframe page. Reports the content height to the parent
 * ONLY after the parent asked ({type: "quellenpanel:hoehe?"}), to that window and origin, and then
 * again whenever the height changes. Other messages and other windows are ignored.
 */
function zielOrigin(origin: string): string {
  // An opaque origin ("null", e.g. a sandboxed or file:// host) cannot be targeted; the height is not secret.
  return origin && origin !== 'null' ? origin : '*';
}

export function hoeheAntworten(ev: MessageEvent, hoehe: number, parent?: Window): boolean {
  const d = ev.data as { type?: unknown } | null;
  if (!d || typeof d !== 'object' || d.type !== 'quellenpanel:hoehe?' || !ev.source) return false;
  if (parent && ev.source !== parent) return false;
  (ev.source as Window).postMessage({ type: 'quellenpanel:hoehe', hoehe }, zielOrigin(ev.origin));
  return true;
}

export function starteEmbed(): void {
  let ziel: { source: Window; origin: string } | null = null;
  // body has auto height (embed.css), so its box shrinks as well as grows, unlike scrollHeight.
  const hoehe = () => Math.ceil(document.body.getBoundingClientRect().height);
  window.addEventListener('message', (ev) => {
    if (hoeheAntworten(ev, hoehe(), window.parent)) ziel = { source: ev.source as Window, origin: zielOrigin(ev.origin) };
  });
  if (typeof ResizeObserver !== 'undefined') {
    let letzte = 0;
    new ResizeObserver(() => {
      const h = hoehe();
      if (ziel && h !== letzte) { letzte = h; ziel.source.postMessage({ type: 'quellenpanel:hoehe', hoehe: h }, ziel.origin); }
    }).observe(document.body);
  }
}
