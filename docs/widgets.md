# Quellenpanel-Widgets einbinden

Das Quellenverzeichnis lässt sich auf jeder Webseite einbinden: als Element mit einem Skript, oder
als iframe. Die leichten Widgets zeigen nur öffentliche Daten (Stufe 0) und senden keine Cookies.
`<wlo-quellen-kacheln>` und `<wlo-quellenpanel>` sind die volle App: Sie bieten die normale
Anmeldung der jeweiligen Instanz an (Partner-Passwort, Team-Login), der Server begrenzt die Daten
weiterhin nach Rolle.

`<host>` steht im Folgenden für die Adresse der öffentlichen Instanz.

## 1. Mit Skript (empfohlen)

Das Skript wird einmal pro Seite eingebunden, danach beliebig viele Elemente:

```html
<script src="https://<host>/widgets/quellenpanel-widgets.js" defer></script>

<wlo-quellen-top fach="Mathematik" max="10"></wlo-quellen-top>
```

Das Skript ist rund 13 KB groß und hat keine Abhängigkeiten. Die Daten kommen von dem Host, von dem
das Skript geladen wurde. Mit `api-base="https://…/api"` lässt sich eine andere Instanz wählen.

### Elemente

| Element | Inhalt | Beispiel |
|---|---|---|
| `<wlo-quellen-liste>` | Suchfeld und kompakte Liste (Name, Fächer, Anzahl Inhalte, Link) | `<wlo-quellen-liste fach="Chemie" max="10">` |
| `<wlo-quellen-liste variante="schlicht" suche="aus">` | Schlichte Liste für helle Hintergründe, ohne Rahmen und ohne Suchfeld | |
| `<wlo-quellen-top>` | Top N der Quellen nach Anzahl der Inhalte, nummeriert (für Fachportale) | `<wlo-quellen-top fach="Biologie" max="10">` |
| `<wlo-quellen-zahl>` | Kennzahl „N Quellen · M Inhalte“ mit Link ins Verzeichnis | `<wlo-quellen-zahl fach="Physik" link="https://…">` |
| `<wlo-quelle>` | Steckbrief einer Quelle | `<wlo-quelle quelle="crawler:bpb_spider">` |
| `<wlo-quellen-statistik>` | Balken der Fächer und Bildungsstufen | `<wlo-quellen-statistik max="8">` |
| `<wlo-quellen-kacheln>` | Kacheln mit Filtern (die Hauptansicht der App) | `<wlo-quellen-kacheln fach="Mathematik">` |
| `<wlo-quellenpanel>` | die ganze App | `<wlo-quellenpanel>` |

`<wlo-quellen-kacheln>` und `<wlo-quellenpanel>` laden beim ersten Vorkommen das große App-Bundle
nach (etwa 1 MB, mit eigenen Schriften und Angular-Laufzeit). Für Seiten, die nur eine Liste
brauchen, sind die leichten Elemente die bessere Wahl. Das große Bundle bringt zone.js mit, das auf
der Gastseite Timer und Promises umhüllt; auf Seiten mit eigener Angular-App ist das iframe die
sicherere Wahl. Die leichten Elemente setzen alle wichtigen Eigenschaften selbst zurück; das große
Bundle erbt dagegen grobe Regeln der Gastseite auf bloße Tags (etwa `div { outline: … }` oder
`p { text-align: center }`). Auf Seiten mit solchen Themes ist das iframe die bessere Wahl.

Das Skript erkennt seine Herkunft über `document.currentScript`. Wird es nicht als normales
`<script src>` eingebunden (zum Beispiel über einen Tag-Manager oder als Modul), muss `api-base`
gesetzt werden. Doppeltes Einbinden schadet nicht.

### Alle Optionen auf einen Blick

Spalten: **L** = leichte Elemente (`wlo-quellen-liste`, `-top`, `-zahl`, `wlo-quelle`,
`-statistik`), **K** = Kacheln und App (`wlo-quellen-kacheln`, `wlo-quellenpanel`),
**i** = iframe-Seite `/embed/<name>?…`, **A** = Link auf die App `https://<host>/?…`.

| Attribut | Werte | Standard | L | K | i | A | Wirkung |
|---|---|---|---|---|---|---|---|
| `fach` | Fachname, z. B. `Mathematik` | alle | ✓ | ✓ | ✓ | – | Vorbelegung Fach |
| `bildungsstufe` | z. B. `Primarstufe`, `Sekundarstufe I` | alle | ✓ | ✓ | ✓ | – | Vorbelegung Bildungsstufe |
| `suche` | Suchbegriff, oder `aus` | leer | ✓ | ✓ | ✓ | – | Vorbelegung Suche; bei der Liste blendet `aus` das Suchfeld aus |
| `nur-oer` | ohne Wert | aus | ✓ | ✓ | ✓ | – | nur Quellen mit offener Lizenz |
| `max` | Zahl 1–50 | 10 (Statistik 8) | ✓ | – | ✓ | – | Anzahl Einträge (Liste, Top, Statistik) |
| `sprache` | `de`, `en` | `de` | ✓ | ✓ | ✓ | – | Sprache der Texte |
| `variante` | `schlicht` | – | ✓ | – | ✓ | – | Liste ohne Rahmen und Hintergrund, für helle Seiten |
| `quelle` | Kennung, z. B. `crawler:bpb_spider` | – | ✓ | – | ✓ | – | nur `wlo-quelle`: welche Quelle (Feld `id` der API) |
| `link` | URL | Quellenverzeichnis | ✓ | – | – | – | nur `wlo-quellen-zahl`: Ziel des Links |
| `farbe` | `#rrggbb` | Markenfarbe des Profils | ✓ | ✓ | ✓ | ✓ | Markenfarbe: Links, Rang, Balken; in K auch Knöpfe, Fokus, Tönungen |
| `hintergrund` | `#rrggbb` | Weiß bzw. Hellgrau (K) | ✓ | ✓ | ✓ | ✓ | Hintergrund des Widgets bzw. der Fläche um Kacheln und Liste |
| `rahmen` | `aus` | an | ✓ | ✓ | ✓ | ✓ | ohne Rahmen, Rundung und Außenabstand, nahtlos in der Seite |
| `kopf` | `aus` | an | – | ✓ | ✓ | ✓ | Kopfzeile mit Logo, Ansicht, Stufe und Sprache ausblenden |
| `fuss` | `aus` | an | – | ✓ | ✓ | ✓ | Fußzeile mit Impressum und Links ausblenden |
| `filter` | `aus` | an | – | ✓ | ✓ | ✓ | Such- und Filterleiste ausblenden (Blättern bleibt) |
| `ansicht` | `kacheln`, `liste` | `kacheln` | – | ✓ | ✓ | ✓ | Ansicht festlegen (wichtig, wenn der Kopf fehlt) |
| `api-base` | URL der API | Herkunft des Skripts | ✓ | ✓ | – | – | API einer anderen Instanz |
| `with-credentials` | `true` | aus | – | ✓ | – | – | Team-Login aus einer fremden Seite (nur mit `QE_ALLOWED_ORIGINS`) |

Regeln:

- **Ausschalten** mit `aus`, `off`, `false`, `0` oder `nein`; jeder andere Wert und das Fehlen des
  Attributs lassen den Teil an.
- **Farben** nur als `#rrggbb`; im Query-String `%23` statt `#` oder die Raute weglassen
  (`hintergrund=ffffff`). Andere Angaben werden ignoriert. Ist die Markenfarbe als Schrift zu hell,
  dunkelt die App sie für Text und Fokus selbst ab, damit der Kontrast reicht.
- **Ohne Kopf** gilt die Basisansicht (Stufe 0), die Ansicht aus `ansicht` und die Sprache aus
  `sprache`; Umschalter gibt es dann nicht.
- **Ändern zur Laufzeit:** Die Attribute lassen sich per JavaScript ändern; leichte Elemente laden
  dann neu.
- **Vorbelegungen** (`fach`, `suche` …) gelten in der App nicht als Query-Parameter, nur als
  Attribut und in der iframe-Seite.

### Rezepte: schlanke Einbettung

Kacheln oder Liste ohne Kopf und Fuß, so dass sich das Verzeichnis wie ein Teil der Seite liest.

Für eine ruhige Einbindung in eine Webseite, etwa auf weißem Hintergrund:

```html
<script src="https://<host>/widgets/quellenpanel-widgets.js" defer></script>

<!-- Kacheln, nur Basisansicht, ohne Kopf, Fuß und Rahmen, auf Weiß -->
<wlo-quellen-kacheln kopf="aus" fuss="aus" rahmen="aus" hintergrund="#ffffff"></wlo-quellen-kacheln>

<!-- dieselbe Ansicht als Liste, ohne Filterleiste, Fach vorbelegt -->
<wlo-quellen-kacheln ansicht="liste" kopf="aus" fuss="aus" filter="aus" rahmen="aus"
                     hintergrund="#ffffff" fach="Chemie"></wlo-quellen-kacheln>

<!-- Fachportal: Top 10 Biologie in der Portalfarbe, ohne Rahmen -->
<wlo-quellen-top fach="Biologie" max="10" farbe="#00508c" rahmen="aus"></wlo-quellen-top>

<!-- schlichte Liste ohne Suchfeld auf hellem Grund -->
<wlo-quellen-liste variante="schlicht" suche="aus" fach="Physik" max="8"></wlo-quellen-liste>
```

Als iframe (zum Beispiel in einem CMS ohne Skripte):

```html
<iframe title="Quellen Mathematik" style="width:100%; border:0; height:900px"
  src="https://<host>/embed/quellen-kacheln?fach=Mathematik&kopf=aus&fuss=aus&rahmen=aus&hintergrund=%23ffffff"></iframe>
```

Als Link auf die ganze App, etwa für einen Menüpunkt:
`https://<host>/?kopf=aus&fuss=aus&ansicht=liste&farbe=%23003b7c`.

Testseite mit diesen Beispielen: `/widgets/beispiele/schlank.html`.

Ohne Kopf gibt es keinen Umschalter für Ansicht, Stufe und Sprache: Es gilt die Basisansicht
(Stufe 0), die Ansicht aus `ansicht` und die Sprache aus `sprache`. Suche und Filter bleiben, solange
`filter` nicht `aus` ist; das Blättern bleibt immer. Dieselben Angaben wirken als Query-Parameter
der iframe-Seite (`/embed/quellen-kacheln?kopf=aus&fuss=aus&rahmen=aus&hintergrund=%23ffffff`) und
der App selbst (`https://<host>/?kopf=aus&ansicht=liste`). Im Query-String wird `#` als `%23`
geschrieben; `hintergrund=ffffff` ohne Raute geht auch.

### Aussehen anpassen

Die Widgets erben die Schrift nicht von der Seite. Farben und Schrift lassen sich über
CSS-Variablen setzen, zum Beispiel:

```css
wlo-quellen-top {
  --wq-font: "Source Sans 3", sans-serif;
  --wq-accent: #00508c;   /* Rang, Kennzahl, Balken */
  --wq-link: #00508c;
  --wq-text: #1d2433;
  --wq-muted: #5b6475;
  --wq-bg: #ffffff;
  --wq-border: #dfe3ea;
  --wq-radius: 10px;
}
```

Weitere Variablen: `--wq-line` (Trennlinien), `--wq-chip` (Hintergrund der Schlagwörter),
`--wq-input-bg`. Alle Styles der Widgets hängen am Element-Selektor; sie verändern die Gastseite
nicht. Regeln der Gastseite mit `!important` können die Widgets überschreiben.

### Sicherheit und CSP der Gastseite

- Das Skript nutzt kein `eval` und kein Inline-Skript. Eine Gastseite mit strenger CSP braucht:
  `script-src https://<host>`, `connect-src https://<host>`, `img-src` für Vorschaubilder.
  Die Styles kommen als Constructable Stylesheet; nur ältere Browser fallen auf ein
  `<style>`-Element zurück (dann ist `style-src 'unsafe-inline'` nötig).
- `<wlo-quellen-kacheln>` und `<wlo-quellenpanel>` brauchen zusätzlich `style-src 'unsafe-inline'`
  (Angular setzt Komponenten-Styles als `<style>`) und `font-src https://<host>`.
- Alle Daten werden als Text eingefügt, Links nur mit `http(s)`; externe Links öffnen in einem
  neuen Tab und sagen das an.
- Es werden keine Cookies gesendet.

## 2. Als iframe

Jedes Element gibt es auch als Seite: `https://<host>/embed/<name>?<attribute>`, zum Beispiel

```html
<iframe title="Top 10 Physik" src="https://<host>/embed/quellen-top?fach=Physik&max=10"
        style="width:100%; border:0; height:600px"></iframe>
```

`<name>` ist der Elementname ohne `wlo-` (`quellen-liste`, `quellen-top`, `quellen-zahl`, `quelle`,
`quellen-statistik`, `quellen-kacheln`, `quellenpanel`). Erlaubt sind die Attribute mit ✓ in Spalte **i** der
Tabelle oben.

**Höhe automatisch anpassen:** Die iframe-Seite meldet ihre Höhe erst, wenn die Gastseite danach
fragt, und danach bei jeder Änderung:

```js
const frame = document.querySelector('iframe');
const herkunft = new URL(frame.src).origin;
addEventListener('message', (ev) => {
  if (ev.source === frame.contentWindow && ev.origin === herkunft && ev.data?.type === 'quellenpanel:hoehe'
      && typeof ev.data.hoehe === 'number') {
    frame.style.height = Math.min(ev.data.hoehe, 5000) + 'px';
  }
});
frame.addEventListener('load', () => frame.contentWindow.postMessage({ type: 'quellenpanel:hoehe?' }, herkunft));
```

**Betrieb:** Welche Seiten einbetten dürfen, regelt `QE_FRAME_ANCESTORS` (CSP `frame-ancestors`,
Leerzeichen-getrennt, Standard `*`; auf der Team-Instanz nur `'self'`).

## 3. Testseiten

Die Instanz liefert drei Testseiten aus:

- `https://<host>/widgets/beispiele/schlank.html`: schlanke Einbettung auf Weiß (Kacheln und
  Liste ohne Kopf, Fuß und Rahmen, leichte Liste in eigener Farbe).
- `https://<host>/widgets/beispiele/leer.html`: alle Elemente auf einer leeren Seite mit strenger
  CSP, dazu ein iframe mit Höhenanpassung.
- `https://<host>/widgets/beispiele/gast.html`: eine Gastseite mit absichtlich aggressiven eigenen
  Styles.
