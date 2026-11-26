/**
 * quellenpanel-widgets.js — entry of the light widget script. Include it once:
 *   <script src="https://<quellenpanel-host>/widgets/quellenpanel-widgets.js" defer></script>
 * and place the elements (see docs/widgets.md). The API base defaults to this script's origin.
 */
import { definiereElemente } from './elements';

const src = (document.currentScript as HTMLScriptElement | null)?.src ?? '';
definiereElemente(src);
