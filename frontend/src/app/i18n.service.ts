import { Injectable, signal } from '@angular/core';

export type Lang = 'de' | 'en';

/**
 * Runtime UI translation. A single `lang` signal drives every `t(key)` call, so the language
 * switches live without a reload (Angular's built-in i18n is compile-time and cannot). Only the
 * UI chrome is translated here — data (subjects, source names, quality values) comes from the
 * backend and stays in its original language, and the Impressum stays German (legal text).
 */
const DICT: Record<string, { de: string; en: string }> = {
  // header / views
  'app.title':            { de: 'Quellenverzeichnis', en: 'Source directory' },
  'view.tiles':           { de: 'Kacheln', en: 'Tiles' },
  'view.list':            { de: 'Liste', en: 'List' },
  'view.stats':           { de: 'Statistiken', en: 'Statistics' },
  'aria.view':            { de: 'Ansicht', en: 'View' },
  'aria.lang':            { de: 'Sprache', en: 'Language' },

  // filters
  'filter.search':        { de: 'Quelle suchen', en: 'Search source' },
  'filter.search.ph':     { de: 'Name, Thema …', en: 'Name, topic …' },
  'filter.sort':          { de: 'Sortierung', en: 'Sort' },
  'filter.sort.content':  { de: 'Inhalte', en: 'Content' },
  'filter.sort.name':     { de: 'Name', en: 'Name' },
  'filter.subject':       { de: 'Fach', en: 'Subject' },
  'filter.subject.all':   { de: 'Alle Fächer', en: 'All subjects' },
  'filter.level':         { de: 'Bildungsstufe', en: 'Educational level' },
  'filter.level.all':     { de: 'Alle Stufen', en: 'All levels' },
  'filter.status':        { de: 'Erschließungsstatus', en: 'Cataloguing status' },
  'filter.all':           { de: 'Alle', en: 'All' },
  'filter.minCount':      { de: 'Min. Inhalte', en: 'Min. content' },
  'filter.oer':           { de: 'nur OER', en: 'OER only' },
  'filter.crawler':       { de: 'nur Crawler', en: 'Crawlers only' },
  'filter.problem':       { de: 'Datenprüfung (Team)', en: 'Data check (team)' },

  // results / units
  'results.count':        { de: 'Quellen', en: 'sources' },
  'action.exportCsv':     { de: 'CSV-Export', en: 'CSV export' },
  'action.exportJson':    { de: 'JSON-Export', en: 'JSON export' },
  'export.table':         { de: 'Tabelle', en: 'Table' },
  'export.tableTitle':    { de: 'Aktuelle Filter-Auswahl als Tabellen-PDF', en: 'Current filter selection as a table PDF' },
  'export.tableDone':     { de: 'Tabelle erzeugt', en: 'Table created' },
  'export.tableEmpty':    { de: 'Keine Quellen im aktuellen Filter.', en: 'No sources in the current filter.' },
  'export.tableError':    { de: 'Tabelle konnte nicht erzeugt werden.', en: 'Could not create the table.' },
  'status.blacklist':     { de: 'Blacklist', en: 'blacklist' },
  'status.mehrfach':      { de: 'Mehrfach', en: 'duplicate' },
  'status.hidden':        { de: 'ausgeblendet', en: 'hidden' },
  // audit report (team)
  'audit.open':           { de: 'Audit-Protokoll', en: 'Audit report' },
  'audit.title':          { de: 'Audit-Protokoll (Datenprobleme)', en: 'Audit report (data problems)' },
  'audit.loading':        { de: 'Protokoll wird erstellt …', en: 'Building report …' },
  'audit.error':          { de: 'Protokoll nicht verfügbar.', en: 'Report unavailable.' },
  'audit.hint':           { de: 'Datenprobleme zur Bereinigung — lesbar, speicherbar (.md) und druckbar.', en: 'Data problems for cleanup — readable, savable (.md) and printable.' },
  'audit.print':          { de: 'Drucken', en: 'Print' },
  'audit.save':           { de: 'Speichern (.md)', en: 'Save (.md)' },
  'results.empty':        { de: 'Keine Quellen für diese Filter gefunden.', en: 'No sources found for these filters.' },
  'error.load':           { de: 'Daten konnten nicht geladen werden. Bitte später erneut versuchen.', en: 'Could not load data. Please try again later.' },
  'unit.content':         { de: 'Inhalte', en: 'content' },

  // tile / list
  'tile.oer':             { de: 'Offene Bildungsressource', en: 'Open Educational Resource' },
  'tile.family':          { de: 'verwandte Quellen (gleiche Bezugsquelle)', en: 'related sources (same publisher)' },
  'col.source':           { de: 'Quelle', en: 'Source' },
  'col.content':          { de: 'Inhalte', en: 'Content' },
  'col.subject':          { de: 'Fach', en: 'Subject' },
  'col.level':            { de: 'Bildungsstufe', en: 'Level' },
  'col.type':             { de: 'Typ', en: 'Type' },
  'col.oer':              { de: 'OER', en: 'OER' },
  'col.status':           { de: 'Status', en: 'Status' },
  'col.quality':          { de: 'Qualität', en: 'Quality' },
  'action.open':          { de: 'Quelle öffnen', en: 'Open source' },
  'action.search':        { de: 'Inhalte in der Suche', en: 'Contents in search' },
  'action.close':         { de: 'Schließen', en: 'Close' },
  'action.cancel':        { de: 'Abbrechen', en: 'Cancel' },

  // access tiers (Basisinfos / Details / Audit)
  'tier.aria':            { de: 'Informationsstufe', en: 'Information tier' },
  'tier.base':            { de: 'Basisinfos', en: 'Basic info' },
  'tier.details':         { de: 'Details', en: 'Details' },
  'tier.audit':           { de: 'Audit', en: 'Audit' },
  'team.login.title':     { de: 'Team-Anmeldung', en: 'Team login' },
  'team.login.password':  { de: 'Passwort', en: 'Password' },
  'team.login.submit':    { de: 'Anmelden', en: 'Sign in' },
  'team.login.error':     { de: 'Falsches Passwort.', en: 'Wrong password.' },
  'detail.field.ki':          { de: 'KI-Nutzung & Recht', en: 'AI usage & law' },
  'detail.ki.hint':           { de: 'Rechts-/Nutzungshinweise der Quelle selbst — Basis der KI-Nutzungs-Einschätzung.', en: 'The source\'s own legal / usage notes — the basis of the AI-usage assessment.' },
  'detail.field.fieldgen':    { de: 'Metadaten-Erzeugung (Crawler-Provenienz)', en: 'Metadata generation (crawler provenance)' },
  'detail.field.fieldsActive':{ de: 'aktive Felder', en: 'active fields' },
  'detail.fieldgen.hint':     { de: 'Je Metadatenfeld, ob und wie der Crawler es erzeugt (gescraped, hart kodiert, gemappt …).', en: 'Per metadata field, whether/how the crawler produces it (scraped, hard-coded, mapped …).' },
  'detail.fg.item':           { de: 'Item', en: 'Item' },
  'detail.fg.field':          { de: 'Feld', en: 'Field' },
  'detail.fg.status':         { de: 'Status', en: 'Status' },
  'detail.fg.gen':            { de: 'Erzeugung', en: 'Generation' },
  'detail.fg.active':         { de: 'aktiv', en: 'active' },
  'detail.fg.fromSource':     { de: 'aus Quelldaten', en: 'from source data' },
  'detail.field.internal':    { de: 'Interne Felder (Team)', en: 'Internal fields (team)' },
  'detail.field.flags':       { de: 'Datenproblem-Marker (Team)', en: 'Data-problem flags (team)' },

  // Audit-tile source-binding badges (Quelldatensatz / Bezugsquelle / Spider)
  'bind.node':            { de: 'Quelldatensatz', en: 'Source record' },
  'bind.bezugsquelle':    { de: 'Bezugsquelle', en: 'Publisher' },
  'bind.spider':          { de: 'Spider / Crawler', en: 'Spider / crawler' },
  'bind.none':            { de: 'fehlt', en: 'missing' },

  // multi-select / Sammel-PDF (tier 1+)
  'select.one':           { de: 'Quelle auswählen', en: 'Select source' },
  'select.selected':      { de: 'ausgewählt', en: 'selected' },
  'select.clear':         { de: 'Auswahl leeren', en: 'Clear selection' },
  'select.pdf':           { de: 'Sammel-PDF', en: 'Bundle PDF' },
  'select.pdfBusy':       { de: 'PDF wird erzeugt …', en: 'Generating PDF …' },
  'select.pdfDone':       { de: 'PDF erzeugt', en: 'PDF created' },
  'select.pdfEmpty':      { de: 'Keine Daten für die Auswahl.', en: 'No data for the selection.' },
  'select.pdfError':      { de: 'PDF konnte nicht erzeugt werden.', en: 'Could not create the PDF.' },

  // stats
  'stats.kpi.sources':    { de: 'Quellen', en: 'Sources' },
  'stats.kpi.content':    { de: 'Inhalte gesamt', en: 'Total content' },
  'stats.kpi.withNode':   { de: 'Mit Quelldatensatz', en: 'With source record' },
  'stats.kpi.oer':        { de: 'OER-Anteil', en: 'OER share' },
  'stats.kpi.crawler':    { de: 'Crawler-Quellen', en: 'Crawler sources' },
  'stats.lane.dist':      { de: 'Inhaltsverteilung', en: 'Content distribution' },
  'stats.lane.topics':    { de: 'Themen & Zielgruppen', en: 'Topics & audiences' },
  'stats.lane.openness':  { de: 'Offenheit & Lizenzen', en: 'Openness & licences' },
  'stats.chart.topSources': { de: 'Top Quellen nach Inhalten', en: 'Top sources by content' },
  'stats.chart.languages':  { de: 'Sprachen', en: 'Languages' },
  'stats.chart.subjects':   { de: 'Top-Fächer', en: 'Top subjects' },
  'stats.chart.levels':     { de: 'Bildungsstufen', en: 'Educational levels' },
  'stats.chart.licenses':   { de: 'Lizenzen', en: 'Licences' },
  'stats.chart.oer':        { de: 'OER-Anteil', en: 'OER share' },
  'stats.loading':        { de: 'Statistiken werden geladen …', en: 'Loading statistics …' },
  // extended overview (tier 1+)
  'stats.tier1.title':    { de: 'Erweiterte Statistik (Details)', en: 'Extended statistics (Details)' },
  'stats.tier2.title':    { de: 'Team-Auswertung (Audit)', en: 'Team analysis (Audit)' },
  'stats.kpi.avgFields':  { de: 'Ø Felder/Crawler', en: 'Avg fields/crawler' },
  'stats.sec.topLists':   { de: 'Top-Listen', en: 'Top lists' },
  'stats.sec.origin':     { de: 'Quellen & Herkunft', en: 'Sources & origin' },
  'stats.sec.brackets':   { de: 'Inhaltsmengen', en: 'Content volumes' },
  'stats.sec.crawler':    { de: 'Metadaten & Crawler', en: 'Metadata & crawlers' },
  'stats.card.quellenverwaltung': { de: 'Quellenverwaltung', en: 'Source management' },
  'stats.card.coverage':  { de: 'Inhaltsabdeckung nach Quellentyp', en: 'Content coverage by source type' },
  'stats.card.brktNode':  { de: 'Quellen × Inhalte (je Quelldatensatz)', en: 'Sources × content (per record)' },
  'stats.card.bqSize':    { de: 'Bezugsquellen × Inhalte', en: 'Publishers × content' },
  'stats.card.fillContent': { de: 'Füllstand: Beschreibung & Auffindbarkeit', en: 'Fill: description & discoverability' },
  'stats.card.fillClass':   { de: 'Füllstand: Einordnung & Qualität', en: 'Fill: classification & quality' },
  'stats.card.method':    { de: 'Daten-Herkunft (Methode)', en: 'Data origin (method)' },
  'stats.card.crawlerType': { de: 'Crawler nach Typ', en: 'Crawlers by type' },
  'stats.qv.all':         { de: 'alle Quellen', en: 'all sources' },
  'stats.qv.node':        { de: 'mit Quelldatensatz', en: 'with source record' },
  'stats.qv.bq':          { de: 'mit Bezugsquelle', en: 'with publisher' },
  'stats.qv.both':        { de: 'Überschneidung', en: 'overlap' },
  'stats.qv.hint':        { de: 'Sichtbare Quellen (aussortierte ausgeblendet) — deckungsgleich mit dem Filter „Art der Quelle".', en: 'Visible sources (sorted-out ones hidden) — matches the "source type" filter.' },
  'stats.cov.bq':         { de: 'über Bezugsquelle', en: 'via publisher' },
  'stats.cov.crawler':    { de: 'über Crawler', en: 'via crawler' },
  'stats.cov.node':       { de: 'mit Quelldatensatz', en: 'with source record' },
  'stats.cov.hint':       { de: 'Erreichbare Inhalte je Quellentyp — die Gruppen überlappen sich.', en: 'Content reachable per source type — the groups overlap.' },
  'stats.fill.nodeHint':  { de: 'Anteil der Quelldatensätze mit gefülltem Feld.', en: 'Share of source datasets with the field filled.' },
  // team addendum (tier 2)
  'stats.team.sec.problems':        { de: 'Datenqualität — Überblick (Team)', en: 'Data quality — overview (team)' },
  'stats.team.sec.problemGroups':   { de: 'Datenprobleme nach Gruppen (Team)', en: 'Data problems by group (team)' },
  'stats.team.sec.problemExamples': { de: 'Datenprobleme — Beispiel-Quellen (Team)', en: 'Data problems — example sources (team)' },
  'stats.team.sec.binding':         { de: 'Spider- & Quell-Bindung (Team)', en: 'Spider & source binding (team)' },
  'stats.team.sec.fill':            { de: 'Feld-Füllstände (Team)', en: 'Field fill levels (team)' },
  'stats.team.sec.dups':            { de: 'Dubletten (Team)', en: 'Duplicates (team)' },
  'stats.team.sec.merge':           { de: 'Wie die Engine die Daten zusammenführt (Team)', en: 'How the engine merges the data (team)' },
  'stats.card.perSource': { de: 'Probleme je Quelle', en: 'Problems per source' },
  'stats.perSource.hint': { de: 'Wie viele Datenprobleme eine Quelle gleichzeitig hat (Provenienz-Marker zählen nicht). Die einzelnen Probleme stehen nach Gruppen darunter.', en: 'How many data problems a source has at once (provenance markers excluded). The individual problems are listed by group below.' },
  'stats.card.spiderBinding': { de: 'Spider-Bindung (am Quelldatensatz)', en: 'Spider binding (on the source dataset)' },
  'stats.spider.gi':      { de: 'Crawler-Kennung gesetzt (general_identifier)', en: 'crawler id set (general_identifier)' },
  'stats.spider.rs':      { de: 'Replikationsquelle gesetzt (replicationsource)', en: 'replication source set (replicationsource)' },
  'stats.spider.both':    { de: 'beide Kennungen gesetzt', en: 'both ids set' },
  'stats.spider.real':    { de: 'tatsächlich an Crawler gebunden', en: 'actually bound to a crawler' },
  'stats.spider.hint':    { de: 'Bindung am Quelldatensatz: „Crawler-Kennung" wird beim Crawlen gesetzt, „Replikationsquelle" auch bei reiner Datenübernahme. „Tatsächlich gebunden" = echte Spider-Kennung (ohne reine WLO-Migration).', en: 'Binding on the source dataset: the "crawler id" is set during crawling, the "replication source" also on plain data import. "Actually bound" = a real spider id (excluding pure WLO migration).' },
  'stats.card.intersection': { de: 'Quelldatensatz × Bezugsquelle — Aufschlüsselung', en: 'Source dataset × publisher — breakdown' },
  'stats.intersection.hint': { de: 'Quelldatensätze mit Bezugsquelle, aufgeschlüsselt. „Erstzuordnung" = erster, sauberer Datensatz je Bezugsquelle (kein Zweit-Datensatz, nicht aussortiert).', en: 'Source datasets that have a publisher, broken down. "First assignment" = the first clean dataset per publisher (not a secondary record, not sorted out).' },
  'stats.herkunft.clean':     { de: 'Erstzuordnung (sauber)', en: 'first assignment (clean)' },
  'stats.herkunft.zweit':     { de: 'Zweit-Datensätze', en: 'secondary records' },
  'stats.herkunft.blacklist': { de: 'aussortiert (Blacklist)', en: 'sorted out (blacklist)' },
  'stats.card.fillKi':    { de: 'KI-/Rechtshinweise (je Crawler)', en: 'AI / legal notes (per crawler)' },
  'stats.fill.hint':      { de: 'Anteil mit gefülltem Feld', en: 'Share with the field filled' },
  'stats.card.dupUrl':    { de: 'Doppelte URLs', en: 'Duplicate URLs' },
  'stats.card.dupTitle':  { de: 'Doppelte Titel', en: 'Duplicate titles' },
  'stats.dup.groups':     { de: 'Gruppen', en: 'groups' },
  'stats.dup.extra':      { de: 'überzählig', en: 'surplus' },
  'stats.examples.affected': { de: 'betroffen', en: 'affected' },

  // detail
  'detail.contentCount':  { de: 'Inhalte in WLO', en: 'Content in WLO' },
  'detail.sec.basic':     { de: 'Grund-Informationen', en: 'Basic information' },
  'detail.sec.education': { de: 'Bildung & Einordnung', en: 'Education & classification' },
  'detail.sec.license':   { de: 'Lizenz', en: 'Licence' },
  'detail.sec.related':   { de: 'Verwandte Quellen', en: 'Related sources' },
  'detail.related.hint':  { de: 'Weitere Quellen unter derselben Bezugsquelle:', en: 'Other sources under the same publisher:' },
  'detail.related.andMore': { de: 'weitere', en: 'more' },
  'detail.related.node':  { de: 'mit Quelldatensatz', en: 'with source dataset' },
  'detail.related.bq':    { de: 'nur Bezugsquelle', en: 'publisher only' },
  'detail.sec.quality':   { de: 'Qualitätsmerkmale', en: 'Quality characteristics' },
  'detail.field.language':{ de: 'Sprache', en: 'Language' },
  'detail.field.bezugsquelle': { de: 'Bezugsquelle', en: 'Publisher' },
  'detail.field.repo':    { de: 'Repository', en: 'Repository' },
  'detail.field.license': { de: 'Lizenz', en: 'Licence' },
  'detail.internal.remarks': { de: 'Bemerkungen', en: 'Remarks' },
  'detail.field.description': { de: 'Beschreibung', en: 'Description' },
  'detail.field.status':  { de: 'Erschließungsstatus', en: 'Cataloguing status' },
  'detail.field.subjects':{ de: 'Fächer', en: 'Subjects' },
  'detail.field.levels':  { de: 'Bildungsstufen', en: 'Educational levels' },
  'detail.field.types':   { de: 'Inhaltstypen', en: 'Content types' },
  'detail.field.keywords':{ de: 'Schlagworte', en: 'Keywords' },
  'detail.field.more':    { de: 'Weitere Angaben', en: 'Further details' },
  'detail.kv.targetGroup':{ de: 'Zielgruppe', en: 'Target group' },
  'detail.kv.curriculum': { de: 'Lehrplanbezug', en: 'Curriculum' },
  'detail.kv.author':     { de: 'Urheber', en: 'Author' },
  'detail.kv.age':        { de: 'Altersgruppe', en: 'Age group' },
  'detail.fromContent.desc': { de: '· Beispiel aus den Inhalten', en: '· example from the content' },
  'detail.fromContent.kw':   { de: '· aus den Inhalten', en: '· from the content' },
  'detail.pdf':           { de: 'Als PDF', en: 'As PDF' },
  'detail.examples':      { de: 'Beispiel-Inhalte aus WLO', en: 'Example content from WLO' },
  'detail.contentLoading':{ de: 'Inhalte werden geladen …', en: 'Loading content …' },
  'detail.contentError':  { de: 'Inhalte derzeit nicht abrufbar.', en: 'Content currently unavailable.' },
  'detail.contentNone':   { de: 'Keine verknüpften Inhalte gefunden.', en: 'No linked content found.' },

  // footer
  'footer.impressum':     { de: 'Impressum', en: 'Imprint' },
  'footer.privacy':       { de: 'Datenschutz', en: 'Privacy' },

  // quality merkmal labels
  'q.kosten':       { de: 'Kosten', en: 'Cost' },
  'q.werbung':      { de: 'Werbung', en: 'Advertising' },
  'q.login':        { de: 'Anmeldung', en: 'Login' },
  'q.dsgvo':        { de: 'Datenschutz (DSGVO)', en: 'Data protection (GDPR)' },
  'q.barrier':      { de: 'Barrierefreiheit', en: 'Accessibility' },
  'q.jugend':       { de: 'Jugendschutz', en: 'Youth protection' },
  'q.person':       { de: 'Persönlichkeitsrechte', en: 'Personality rights' },
  'q.straf':        { de: 'Strafrecht', en: 'Criminal law' },
  'q.urheber':      { de: 'Urheberrecht', en: 'Copyright' },
  'q.dsRecht':      { de: 'Datenschutz (rechtlich)', en: 'Data protection (legal)' },
  'q.bildung':      { de: 'Für Bildung geeignet', en: 'Suitable for education' },
  'q.aktuell':      { de: 'Aktualität', en: 'Currency' },
  'q.sach':         { de: 'Sachrichtigkeit', en: 'Factual accuracy' },
  'q.neutral':      { de: 'Neutralität', en: 'Neutrality' },
  'q.transparenz':  { de: 'Anbieter-Transparenz', en: 'Provider transparency' },
  'q.didaktik':     { de: 'Didaktik/Methodik', en: 'Didactics/methodology' },
  'q.medial':       { de: 'Medial passend', en: 'Media suitability' },
  'q.sprache':      { de: 'Sprachl. Angemessenheit', en: 'Language appropriateness' },
  'q.group.access': { de: 'Zugänglichkeit & Zugang', en: 'Accessibility & access' },
  'q.group.legal':  { de: 'Rechtliche Merkmale', en: 'Legal characteristics' },
  'q.group.content':{ de: 'Inhaltliche Qualität', en: 'Content quality' },
};

/**
 * English renderings of the closed quality-VALUE vocabulary (the backend delivers these in
 * German). German display keeps the source value verbatim; English is looked up here and falls
 * back to the German if a value is ever added that is not yet translated.
 */
const QVALUES: Record<string, string> = {
  'nein': 'no',
  'ja': 'yes',
  'null': '—',
  'ohne Anmeldung': 'no login required',
  'Anmeldung erforderlich für erweiterte Funktionen': 'login required for advanced features',
  'Anmeldung notwendig': 'login required',
  'zusätzliche Inhalte / Features per Kauf möglich': 'extra content / features available for purchase',
  'ohne Werbung': 'no advertising',
  'enthält zurückhaltend Werbung': 'contains restrained advertising',
  'zurückhaltende für Zielgruppe geeignete Werbung': 'restrained, audience-appropriate advertising',
  'enthält störend Werbung': 'contains disruptive advertising',
  'Inhalt ist kaum von Werbung unterscheidbar': 'content barely distinguishable from advertising',
  'Datensparsam': 'data-minimising',
  'Nicht DSGVO geprüft': 'not GDPR-checked',
  'Ja - geeignet': 'yes - suitable',
  'Nein - unauffällig': 'no - inconspicuous',
  'Nicht geprüft': 'not checked',
  'A (am niedrigsten)': 'A (lowest)',
  'AA (mittel)': 'AA (medium)',
  'AAA (am höchsten)': 'AAA (highest)',
  'WCAG': 'WCAG',
  'BITV 2.0 (2019)': 'BITV 2.0 (2019)',
  '2-A veraltete Darstellung, inhaltlich noch aktuell': '2-A outdated presentation, still factually current',
  '3-A zeitlos aktuell': '3-A timelessly current',
  '4- aktueller Wissensstand': '4- current state of knowledge',
  '5 - hochaktuell/neuester Wissensstand': '5 - highly current / latest knowledge',
  '3-S angemessen': '3-S appropriate',
  '4-S leicht verständlich, sprachlich korrekt': '4-S easy to understand, linguistically correct',
  '5-S Zielgruppengerechte Sprache': '5-S audience-appropriate language',
  '3-N ideologisch eingefärbt, aber transparent': '3-N ideologically tinged but transparent',
  '4-N neutrale Formulierung': '4-N neutral wording',
  '5-N neutrale Formulierung, unabhängiger Ersteller': '5-N neutral wording, independent author',
  '2-T Anbieter benannt, Kontaktangaben vorhanden': '2-T provider named, contact details present',
  '3-T Anbieter benannt, umfangreiche Kontaktangaben': '3-T provider named, extensive contact details',
  '4-T Anbieter bekannt, umfangreiche Kontaktangaben': '4-T provider known, extensive contact details',
  '5-T renommierter Anbieter, korrekte Kontaktangaben': '5-T reputable provider, correct contact details',
  '2-M angemessene Methodik': '2-M adequate methodology',
  '3-M gute Methodik': '3-M good methodology',
  '4-M moderne, gute Methodik': '4-M modern, good methodology',
  '5-M moderne, sehr gute Methodik': '5-M modern, very good methodology',
  '4-ME Medial gut': '4-ME media: good',
  '4-ME Medial passend': '4-ME media: suitable',
  '5-ME Medial hervorragend': '5-ME media: excellent',
  '4-R sachlich richtig, keine/wenige Belege angeführt': '4-R factually correct, few/no sources cited',
  '5-R wissenschaftlich belegt': '5-R scientifically substantiated',
  '4-D angemessen viele Daten mit Einverständis': '4-D reasonable amount of data with consent',
  '5-D keinerlei Datenweitergabe': '5-D no data sharing whatsoever',
};

@Injectable({ providedIn: 'root' })
export class I18n {
  readonly lang = signal<Lang>('de');

  constructor() {
    try {
      const saved = localStorage.getItem('wlo-lang');
      if (saved === 'de' || saved === 'en') { this.lang.set(saved); }
    } catch { /* localStorage unavailable (e.g. private mode) — keep the default */ }
  }

  set(l: Lang): void {
    this.lang.set(l);
    try { localStorage.setItem('wlo-lang', l); } catch { /* ignore */ }
  }

  /** Translate a UI key to the current language; unknown keys fall back to the key itself. */
  t(key: string): string {
    return DICT[key]?.[this.lang()] ?? key;
  }

  /** Render a backend quality VALUE: German stays verbatim, English is looked up (or falls back). */
  tValue(value: string): string {
    return this.lang() === 'en' ? (QVALUES[value] ?? value) : value;
  }
}
