"""protokoll.py — the team error/data-problem protocol (Markdown).

A pure builder over the records: for every problem category it emits the count, a short
description, ONE Handlungsempfehlung, and a table of the affected sources. Where the data
allows, each case carries a CONCRETE fix hint (which fields are missing, which duplicate to
remove, which record to merge into). Categories are matched by a record flag or a computed
predicate. Adds a metadata fill-rate section and notes the catalog problems that are NOT
per-record detectable. Team-only — served via an authenticated route; pure & unit-testable.
"""
from collections import defaultdict

from stats_common import _FUELL_META

# Per-category long lists are capped (sorted by content) to keep the file usable; the full
# count is always shown in the heading and the overview, so nothing is silently dropped.
CAP = 300


# (key, Rubrik, problem description, single Handlungsempfehlung, flag).
#   flag: the record flag marking this category (set in truth._mark_data_problems / truth_record).
#   Every rubric maps 1:1 to a flag, so the team filter (flag=<NAME>) covers all of them.
# No inner double quotes in the strings (they would clash with the Python delimiter).
CATALOG = [
    ("WLO_MIGRATION", "Als Datenmigration getaggt",
     "Die Bezugsquelle am Quelldatensatz ist der WirLernenOnline-Migrations-Platzhalter, "
     "obwohl die echte Bezugsquelle der Inhalte bekannt ist (siehe Spalte Bezugsquelle).",
     "Bezugsquelle (ccm:oeh_publisher_combined) am Quelldatensatz auf den Wert der Spalte "
     "Bezugsquelle setzen — sofern noch kein anderer Quelldatensatz mit der richtigen "
     "Bezugsquelle existiert.", "WLO_MIGRATION"),
    ("FEHLTAGGING", "Misch-Typen (Quelle + weitere Inhaltstypen)",
     "Der Datensatz trägt den Inhaltstyp Quelle UND weitere Inhaltstypen — Quelle und Inhalt "
     "zugleich, nicht trennbar.",
     "Bei der Quelle ausschließlich den Typ Quelle behalten und die übrigen, in der Spalte "
     "Inhaltstypen genannten Typen entfernen.", "FEHLTAGGING"),
    ("DUBLETTE_VERDACHT", "Dubletten-Verdacht (gleiche URL/Titel)",
     "Mehrere Datensätze teilen dieselbe URL oder denselben Titel.",
     "Pro Gruppe die mit ✅ markierte Quelle behalten und die mit 🗑 markierte(n) Dublette(n) "
     "entfernen (Blacklist-Vorschlag der Kuration ist berücksichtigt).", "DUBLETTE_VERDACHT"),
    ("ZWEITDATENSATZ", "Zweit-Datensätze (mehrere Datensätze je Bezugsquelle)",
     "Weiterer Quelldatensatz, dessen Bezugsquelle schon von einem Primär-Datensatz belegt "
     "ist (die Inhalte zählen dort).",
     "Prüfen, ob eigenständige Quelle (z. B. ein anderer YouTube-Kanal) → behalten; sonst in "
     "den Primär-Datensatz aus der Spalte zusammenführen-in überführen.", "ZWEITDATENSATZ"),
    ("QD_OHNE_BEZUGSQUELLE", "Quelldatensatz ohne Bezugsquelle",
     "Eigener Quelldatensatz, aber keine Bezugsquelle hinterlegt.",
     "Bezugsquelle-Tag am Quelldatensatz ergänzen (passend zu den Inhalten).",
     "QD_OHNE_BEZUGSQUELLE"),
    ("OHNE_STATUS", "Quelldatensatz ohne Erschließungsstatus",
     "Eigener Quelldatensatz, aber kein Erschließungsstatus gesetzt (Status-Lücke; teils "
     "wirkt der Wert 9 wie ein Default).",
     "Erschließungsstatus am Quelldatensatz redaktionell setzen.", "OHNE_STATUS"),
    ("STATUS_INKONSISTENT", "Status-Inkonsistenz: voll gefüllt, aber Status < 9",
     "Kernfelder (Beschreibung/Fächer/Bildungsstufen) sind gefüllt, der Erschließungsstatus "
     "steht aber unter 9 — Metadaten-Stand und Status passen nicht zusammen.",
     "Erschließungsstatus an den tatsächlichen (vollständigen) Bearbeitungsstand angleichen.",
     "STATUS_INKONSISTENT"),
    ("NICHT_PUBLIZIERT", "Quelldatensatz nicht in der Suche veröffentlicht",
     "Workflow-Status ist nicht 150_PUBLISH_IN_SEARCH/155 — der Quelldatensatz taucht in der "
     "Suche nicht auf (als Quelle unsichtbar), unabhängig von den Inhalten.",
     "Quelldatensatz für die Suche freigeben (Workflow auf Publish), sofern er sichtbar sein soll.",
     "NICHT_PUBLIZIERT"),
    ("TYP_NICHT_QUELLE", "Echte Bindung, aber Inhaltstyp ist nicht Quelle",
     "Crawler-/Spider-gebundener Datensatz, dessen Inhaltstyp nicht Quelle ist.",
     "Inhaltstyp am Datensatz auf Quelle ändern — die aktuell gesetzten Typen stehen in der "
     "Spalte Inhaltstypen.", "TYP_NICHT_QUELLE"),
    ("METADATEN_DUENN", "Dünne Metadaten (Kernfelder fehlen)",
     "Quelldatensatz ohne Beschreibung / Fächer / Bildungsstufen.",
     "Die in der Spalte fehlende-Kernfelder genannten Felder am Quelldatensatz ergänzen "
     "(siehe auch Füllstand-Sektion unten).", "METADATEN_DUENN"),
    ("BINDUNG_UNVOLLSTAENDIG", "Crawler ohne Quelldatensatz (such-unsichtbar)",
     "Crawler-Quelle ohne eigenen Quelldatensatz-Knoten — in der Suche nicht auffindbar.",
     "Quelldatensatz (Inhaltstyp Quelle) für den Crawler anlegen, damit die Quelle auffindbar wird.",
     "BINDUNG_UNVOLLSTAENDIG"),
    ("BQ_OHNE_QD", "Bezugsquelle mit Inhalten, aber ohne Quelldatensatz (such-unsichtbar)",
     "Eine Bezugsquelle (Herausgeber-Tag) trägt mehrere Inhalte, hat aber keinen eigenen "
     "Quelldatensatz-Knoten — als Quelle nicht auffindbar/verwaltbar (Pendant zu Crawler ohne "
     "Quelldatensatz, nur herausgeberseitig).",
     "Prüfen, ob eine eigene Quelle (Quelldatensatz, Inhaltstyp Quelle) anzulegen ist; sonst die "
     "Inhalte einer bestehenden Quelle zuordnen.", "BQ_OHNE_QD"),
    ("LEGACY_BINDUNG", "Über alte Verschlagwortung gebunden (Legacy-Vocab)",
     "Bindung über einen alten Vokabular-Eintrag (…/vocabs/sources/<uuid>) statt einen "
     "technischen Spider.",
     "Legacy-Bindung prüfen → auf eine echte Crawler-Bindung bzw. Register-ID migrieren oder "
     "stilllegen.", "LEGACY_BINDUNG"),
    ("SPIDER_UNEINDEUTIG", "Spider-Bindung uneindeutig (general_identifier ≠ replicationsource)",
     "general_identifier und replicationsource am Knoten widersprechen sich — die technische "
     "Bindung ist mehrdeutig (meist Migrations-Platzhalter in replicationsource, echter Spider "
     "in general_identifier).",
     "Als echte Bindung den general_identifier verwenden (Spalte echte Bindung) und "
     "replicationsource entsprechend korrigieren.", "SPIDER_UNEINDEUTIG"),
    ("BQ_EINZELINHALT", "Bezugsquelle mit nur 1 Inhalt (Tagging-Artefakt)",
     "Bezugsquelle-Facette mit höchstens 1 Inhalt und ohne eigenen Quelldatensatz — meist ein "
     "Tagging-Artefakt, keine echte Quelle.",
     "Prüfen, ob echte Quelle; sonst das Bezugsquelle-Tag am Inhalt bereinigen bzw. mit der "
     "richtigen Bezugsquelle zusammenführen.", "BQ_EINZELINHALT"),
    ("BQ_SUBCHANNEL", "Bezugsquelle evtl. Sub-Channel einer Hauptquelle",
     "Die Bezugsquelle sieht aus wie ein Unterkanal/Unterportal einer bereits existierenden "
     "Hauptquelle — das Präfix vor dem Trenner ist selbst eine Bezugsquelle (z. B. YouTube-Kanäle, "
     "Unterportale).",
     "Prüfen, ob unter die Eltern-Bezugsquelle (Spalte Eltern-BQ) zusammenführen — oder bewusst "
     "als eigene Quelle behalten (z. B. ein eigenständiger YouTube-Kanal).", "BQ_SUBCHANNEL"),
    ("BLACKLIST", "Aussortiert (keine echte Quelle / Dublette)",
     "Per Kuration als Nicht-Quelle bzw. Dublette markiert (Einzelmaterial, Serien-Episode …).",
     "Bestätigen oder rehabilitieren; bei bestätigter Nicht-Quelle aus dem Bestand entfernen.",
     "BLACKLIST"),
]

# Categories that gain an extra per-case column with the concrete fix detail.
DETAIL_LABEL = {
    "METADATEN_DUENN": "fehlende Kernfelder",
    "FEHLTAGGING": "Inhaltstypen (außer Quelle entfernen)",
    "TYP_NICHT_QUELLE": "Inhaltstypen (auf Quelle ändern)",
    "ZWEITDATENSATZ": "zusammenführen in (Primär-Datensatz)",
    "SPIDER_UNEINDEUTIG": "echte Bindung (general_identifier)",
    "STATUS_INKONSISTENT": "Erschließungsstatus",
    "NICHT_PUBLIZIERT": "Workflow-Status",
    "BQ_SUBCHANNEL": "Eltern-BQ (Verdacht)",
}


def _matches(r, match):
    return match in r.get("flags", [])


def _md(s) -> str:
    """Escape a value for a markdown table cell (no pipe/newline breaks)."""
    return str(s if s not in (None, "") else "–").replace("|", "\\|").replace("\n", " ").strip()


def _primary_by_bq(records):
    """For each Bezugsquelle, the non-secondary record that holds the content (most content
    wins) — the concrete merge target for its secondary datasets."""
    m = {}
    for r in records:
        if "ZWEITDATENSATZ" in r.get("flags", []):
            continue
        bq = (r["identity"].get("bezugsquelle") or "").strip().lower()
        if not bq:
            continue
        cur = m.get(bq)
        if cur is None or (r.get("contentCount") or 0) > (cur.get("contentCount") or 0):
            m[bq] = r
    return m


def _detail(key, r, primary_by_bq):
    """The concrete per-case fix hint for the categories in DETAIL_LABEL (raw string)."""
    pub = r["public"]
    if key == "METADATEN_DUENN":
        miss = [lbl for lbl, k in (("Beschreibung", "Beschreibung"), ("Fächer", "Faecher"),
                                   ("Bildungsstufen", "Bildungsstufen")) if not pub.get(k)]
        return ", ".join(miss) or "–"
    if key in ("FEHLTAGGING", "TYP_NICHT_QUELLE"):
        return ", ".join(pub.get("Inhaltstypen", [])) or "–"
    if key == "ZWEITDATENSATZ":
        prim = primary_by_bq.get((r["identity"].get("bezugsquelle") or "").strip().lower())
        return prim["name"] if prim else "–"
    inT = r.get("internal") or {}
    if key == "SPIDER_UNEINDEUTIG":
        return inT.get("general_identifier") or "–"
    if key == "STATUS_INKONSISTENT":
        return inT.get("Erschliessungsstatus (genau)") or "–"
    if key == "NICHT_PUBLIZIERT":
        return inT.get("Workflow-Status") or "–"
    if key == "BQ_SUBCHANNEL":
        bq = r["identity"].get("bezugsquelle") or ""
        for sep in (" - ", " – ", " — ", " | "):
            if sep in bq:
                return bq.split(sep)[0].strip()
        return "–"
    return "–"


def _case_table(cases, key, primary_by_bq):
    cases = sorted(cases, key=lambda r: -(r.get("contentCount") or 0))
    label = DETAIL_LABEL.get(key)
    out = [f"| Quelle | Node-ID | Bezugsquelle | Inhalte |{f' {label} |' if label else ''}",
           f"|---|---|---|---|{'---|' if label else ''}"]
    for r in cases[:CAP]:
        idn = r["identity"]
        row = (f"| {_md(r.get('name'))} | {_md(idn.get('nodeId'))} | "
               f"{_md(idn.get('bezugsquelle'))} | {r.get('contentCount') or 0} |")
        if label:
            row += f" {_md(_detail(key, r, primary_by_bq))} |"
        out.append(row)
    if len(cases) > CAP:
        out.append(f"\n_… und {len(cases) - CAP} weitere (gekürzt auf {CAP}, nach Inhalten sortiert)._")
    return out


def _keeper(members):
    """The record to keep in a duplicate group: non-blacklist, then most content, then has a node."""
    return sorted(members, key=lambda r: ("BLACKLIST" in r.get("flags", []),
                                          -(r.get("contentCount") or 0),
                                          not r["identity"].get("nodeId")))[0]


def _url(r):
    return (r["identity"].get("url") or r["public"].get("URL") or "").strip()


def _dubletten(cases):
    """Cluster the duplicate suspects and, per cluster, name the concrete keeper (✅) and the
    duplicate(s) to remove (🗑).

    The build flags DUBLETTE_VERDACHT on collision of URL OR title (truth.py). Two records may
    therefore be linked transitively (A shares a URL with B, B shares a title with C). Grouping
    by a single key would split such chains and silently drop members, so we union records that
    share a URL or a (case-insensitive) title into clusters — every flagged case lands in exactly
    one cluster.
    """
    parent = list(range(len(cases)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_url, by_title = {}, {}
    for i, r in enumerate(cases):
        for index, val in ((by_url, _url(r)), (by_title, (r.get("name") or "").strip().lower())):
            if not val:
                continue
            if val in index:
                parent[find(i)] = find(index[val])
            else:
                index[val] = i

    clusters = defaultdict(list)
    for i, r in enumerate(cases):
        clusters[find(i)].append(r)

    out = []
    for members in sorted(clusters.values(), key=lambda m: -len(m)):
        if len(members) < 2:
            continue
        keeper = _keeper(members)
        label = _url(keeper) or ("Titel: " + (keeper.get("name") or "").strip())
        out.append(f"\n**Gruppe — {_md(label)}** ({len(members)} Kandidaten)")
        out.append(f"- ✅ **behalten:** {_md(keeper.get('name'))} "
                   f"(Node {_md(keeper['identity'].get('nodeId'))}, {keeper.get('contentCount') or 0} Inhalte)")
        for r in members:
            if r is keeper:
                continue
            bl = " — von der Kuration als Dublette markiert (Blacklist)" if "BLACKLIST" in r.get("flags", []) else ""
            out.append(f"- 🗑 **Dublette (entfernen/prüfen):** {_md(r.get('name'))} "
                       f"(Node {_md(r['identity'].get('nodeId'))}){bl}")
    return out


def _fuellstand_section(records):
    """Aggregate fill rate of the important metadata fields over the source datasets —
    weakest first, flagging fields under 50 %."""
    nodes = [r for r in records if r["identity"].get("nodeId")]
    base = max(1, len(nodes))
    rows = sorted(((label, sum(1 for r in nodes if r["public"].get(key) not in (None, "", [], False)))
                   for label, key in _FUELL_META), key=lambda x: x[1])
    out = ["## Metadaten-Füllstand (Quelldatensätze)", "",
           f"Anteil der {len(nodes)} Quelldatensätze mit gefülltem Feld — schwächste zuerst. "
           "Felder unter 50 % (⚠) erschweren Suche, Filter und Vererbung.", "",
           "| Feld | gefüllt | Anteil |", "|---|---|---|"]
    for label, n in rows:
        pct = round(100 * n / base)
        out.append(f"| {label}{' ⚠' if pct < 50 else ''} | {n} | {pct} % |")
    out.append("")
    return out


def _nicht_pruefbar():
    """Catalog problems that are structural and need governance/process work, not per-record detection."""
    return [
        "## Nicht automatisch pro Quelle prüfbar (Governance / Prozess / Technik)", "",
        "Diese Katalog-Probleme sind strukturell und brauchen redaktionelle bzw. konzeptionelle "
        "Klärung statt einer Pro-Record-Erkennung:", "",
        "- **Begriff Quelle nicht abschließend definiert** (Governance) — inkl. Plattform-Frage (YouTube/Kanal/Herausgeber).",
        "- **Drei parallele Abbildungswege** (Quelldatensatz/Bezugsquelle/Spider) nicht deckungsgleich (Modell).",
        "- **Freitext-Bezugsquelle ohne ID** → Schreibvarianten (z. B. Wikipedia ×3); ein Quellen-Register/kontrolliertes Vokabular nötig.",
        "- **Keine erzwingenden Workflows** beim Anlegen/Taggen (Prozess).",
        "- **Korrektur crawler-gebundener Daten blockiert** (Schreibschutz) — Rechte-/Workflow-Designproblem.",
        "- **Anzeige-/Tooling-Themen** (Technik).",
        "",
    ]


def _sections(records):
    """Every catalog rubric with its matched cases — the ONE case collection shared by the
    readable (.md) and the machine-readable (.json/.csv) protocol, so they never diverge."""
    return [(key, title, desc, rec, [r for r in records if _matches(r, match)])
            for key, title, desc, rec, match in CATALOG]


def build_protokoll_data(records, meta) -> dict:
    """Machine-readable protocol (feeds /api/protokoll.json and the flat .csv): the same catalog,
    counts and per-case fix details as the Markdown, as plain data — and deliberately UNCAPPED
    (the .md truncates long tables at 300 for readability; a consuming app needs every case).
    Duplicate clustering (the .md's keep/remove groups) is not replicated — DUBLETTE_VERDACHT
    cases are listed flat like every other rubric."""
    primary_by_bq = _primary_by_bq(records)
    sections = _sections(records)
    categories = []
    for key, title, desc, rec, cases in sections:
        detailed = key in DETAIL_LABEL
        categories.append({
            "key": key, "title": title, "problem": desc, "recommendation": rec,
            "detailLabel": DETAIL_LABEL.get(key), "count": len(cases),
            "cases": [{
                "id": r["id"], "name": r.get("name", ""),
                "nodeId": r["identity"].get("nodeId", ""),
                "bezugsquelle": r["identity"].get("bezugsquelle", ""),
                "contentCount": r.get("contentCount") or 0,
                "detail": _detail(key, r, primary_by_bq) if detailed else None,
            } for r in sorted(cases, key=lambda r: -(r.get("contentCount") or 0))],
        })
    problem_ids = {c["id"] for cat in categories for c in cat["cases"]}
    return {"generatedAt": meta.get("generatedAt", ""), "recordsTotal": len(records),
            "recordsWithProblems": len(problem_ids), "categories": categories}


def build_protokoll(records, meta) -> str:
    primary_by_bq = _primary_by_bq(records)
    sections = _sections(records)
    problem_ids = {r["id"] for _k, _t, _d, _r, cases in sections for r in cases}

    L = ["# Fehler-Protokoll — Datenprobleme bei WLO-Quellen", ""]
    L.append(f"Datenstand: {meta.get('generatedAt', '?')} · Quellen-Records gesamt: "
             f"{len(records)} · mit mindestens einem Datenproblem: {len(problem_ids)}")
    L.append("")
    L.append("> Zählungen über **alle** Records (auch standardmäßig ausgeblendete "
             "Zweit-Datensätze und aussortierte). Eine Quelle kann mehrere Probleme tragen. Wo "
             "die Daten es zulassen, steht je Fall ein konkreter Fix-Hinweis (welche Felder "
             "fehlen, welche Dublette entfernen, in welchen Datensatz zusammenführen).")
    L.append("")
    L.append("## Übersicht (Quantifizierung)")
    L.append("")
    L.append("| # | Rubrik | Kennung | Fälle |")
    L.append("|---|---|---|---|")
    for i, (key, title, _d, _r, cases) in enumerate(sections, 1):
        L.append(f"| {i} | {title} | `{key}` | {len(cases)} |")
    L.append("")

    for i, (key, title, desc, rec, cases) in enumerate(sections, 1):
        L.append(f"## {i}. {title} ({len(cases)})")
        L.append("")
        L.append(f"**Problem:** {desc}")
        L.append("")
        L.append(f"**Handlungsempfehlung:** {rec}")
        L.append("")
        if not cases:
            L.append("_Keine Fälle._")
        elif key == "DUBLETTE_VERDACHT":
            L.extend(_dubletten(cases))
        else:
            L.extend(_case_table(cases, key, primary_by_bq))
        L.append("")

    L.extend(_fuellstand_section(records))
    L.extend(_nicht_pruefbar())
    return "\n".join(L)
