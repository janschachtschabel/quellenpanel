/**
 * quellenpanel-widgets.js — entry of the light widget script. Include it once:
 *   <script src="https://<quellenpanel-host>/widgets/quellenpanel-widgets.js" defer></script>
 * and place the elements (see docs/widgets.md). The API base defaults to this script's origin.
 * Including it twice is harmless: the second copy does nothing.
 */
import { definiereElemente } from './elements';

const w = window as unknown as { __quellenpanelWidgets?: boolean };
if (!w.__quellenpanelWidgets) {
  w.__quellenpanelWidgets = true;
  definiereElemente((document.currentScript as HTMLScriptElement | null)?.src ?? '');
}
