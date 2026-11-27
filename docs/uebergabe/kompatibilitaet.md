# Kompatibilitätsmatrix: Zeile Quellenpanel

Eintrag für die gemeinsame Tabelle aller Dienste (Diensteleitfaden, Kapitel 6).

| Dienst-ID | braucht Dienste | Rechte am Schlüssel | Delegations-Scopes | LLM-Route | Repository-Bezug | nur gemeinsam mit |
|---|---|---|---|---|---|---|
| `quellenpanel` | keine | keine (läuft ohne b-api) | keine | keine | direkt (öffentliche REST-API des Repositorys, nur lesend, anonym) | – |

Erläuterung:

- **braucht Dienste:** Kein anderer Dienst hinter der b-api. Die drei Instanzen (team, partner,
  public) sind ein Dienst aus einem Image; Partner und Öffentlich holen ihren Export von der
  Team-Instanz desselben Release.
- **Repository-Bezug „direkt“:** Die Team-Instanz liest Quelldatensätze, Facetten und
  Node-Metadaten über die öffentliche Such- und Node-API (`QE_REPO_URL`). Partner und Öffentlich
  rufen das Repository nur für Beispielinhalte einer Quelle und für Vorschaubilder auf. Welche
  Felder gelesen werden, legt das Repository-Profil fest (`profiles/<name>/profil.toml`), damit
  läuft der Dienst auch gegen andere edu-sharing-Repositorys. Beim Datenaufbau liest das Team
  zusätzlich das Quellen-Vokabular (`vocabs.openeduhub.de`, ebenfalls aus dem Profil).
- **Rechte:** Personen brauchen keine Rechte am Repository. Der Zugang zu Stufe 1 und 2 läuft
  über Passwörter der jeweiligen Instanz, nicht über Schlüssel der b-api.
