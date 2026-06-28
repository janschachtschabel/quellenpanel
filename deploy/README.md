# Deployment auf Debian 13 (Docker Compose)

Ein einzelner Container liefert die **3-Tier-API** und das **gebaute Angular-Frontend**
samt mitgeliefertem Datenstand aus. Die Zugriffs-Passwörter werden **nicht** ins Image
gebacken, sondern beim Start über `.env` gesetzt (fail closed: ohne Passwort nur die
öffentliche End-User-Ansicht).

Auf dem Server werden nur **zwei Dateien** gebraucht: `docker-compose.yml`
und `.env` (kopiert aus `.env.example`).

## 1. Docker installieren (Debian 13 „Trixie")

Über das **offizielle Docker-Repo** (liefert Engine *und* das `docker compose`-Plugin —
ein Debian-Paket `docker-compose-v2` gibt es auf Trixie nicht):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
docker compose version          # prüfen
```

> Falls `apt-get update` fürs Docker-Repo fehlschlägt (für `trixie` noch keine
> Pakete): in `/etc/apt/sources.list.d/docker.list` `trixie` durch `bookworm`
> ersetzen und `sudo apt-get update` erneut ausführen.

Optional ohne `sudo` arbeiten (danach einmal ab- und wieder anmelden):

```bash
sudo usermod -aG docker $USER
```

## 2. Deploy-Dateien auf den Server bringen

Entweder das Repo klonen …

```bash
git clone <DEIN-GIT-REPO>/quellenpanel.git
cd quellenpanel/deploy
```

… oder nur `docker-compose.yml` + `.env.example` (für HTTPS zusätzlich
`docker-compose.tls.yml` + `Caddyfile`) aus diesem `deploy/`-Ordner per `scp`
in ein Verzeichnis auf dem Server kopieren.

## 3. Konfigurieren

```bash
cp .env.example .env
nano .env
```

In `.env` eintragen:

| Variable | Bedeutung |
|---|---|
| `IMAGE` | `DEINUSER/quellenpanel:latest` — deinen Docker-Hub-Benutzer einsetzen |
| `PORT` | Host-Port (Default `8080`) |
| `QE_TEAM_PASSWORD` | Tier 2 (Audit/Team): Passwort schaltet den Team-Login frei. Leer ⇒ kein Team-Zugriff. |
| `QE_TIER1_PASSWORD` | Tier 1 (Details): optionales Passwort-Gate. Leer ⇒ Tier 1 offen für alle. |
| `QE_PUBLIC_ONLY` | `1` kappt jeden Request hart auf Tier 0 (öffentlich/eingebettet). Leer ⇒ aus. |
| `QE_ALLOWED_ORIGINS` | Komma-getrennte Origins, die einen Cross-Origin-Team-Login (eingebettetes Widget auf anderer Domain) per Cookie nutzen dürfen. Benötigt HTTPS. Leer ⇒ Team-Login nur same-origin. Öffentlicher Lesezugriff bleibt für alle offen. |
| `QE_AUTO_REFRESH_HOUR` | optionaler nächtlicher Auto-Refresh (Stunde 0–23; leer = aus) |

> Ist das Docker-Hub-Repo **privat**, vorher einmalig anmelden: `docker login`.

## 4. Starten

```bash
sudo docker compose pull
sudo docker compose up -d
sudo docker compose ps
```

Prüfen:

```bash
curl -s http://localhost:8080/api/health; echo
```

→ liefert `{"status":"ok",…}`. Im Browser: `http://<SERVER-IP>:8080`

Firewall (falls `ufw` aktiv ist):

```bash
sudo ufw allow 8080/tcp
```

## 5. HTTPS via nip.io (optional, ohne eigene Domain)

`nip.io` ist Wildcard-DNS: `<label>.<DEINE-IP>.nip.io` zeigt automatisch auf deine
Server-IP — damit kann Let's Encrypt ein gültiges Zertifikat ausstellen, ohne dass
du eine Domain kaufst. Ein **Caddy**-Reverse-Proxy davor holt das Zertifikat
automatisch. Dafür liegen **`docker-compose.tls.yml`** + **`Caddyfile`** in diesem
Ordner bereit.

Voraussetzung: **Ports 80 und 443** offen (VPS-Firewall *und* Hoster-Firewall) und
nichts anderes lauscht dort.

```bash
# in .env zusätzlich setzen (IP einsetzen, Punkte bleiben Punkte):
#   SITE_ADDRESS=quellenpanel.31.70.69.94.nip.io
sudo ufw allow 80,443/tcp
sudo docker compose -f docker-compose.tls.yml up -d
sudo docker compose -f docker-compose.tls.yml logs -f caddy   # "certificate obtained" abwarten
```

Danach erreichbar unter `https://quellenpanel.<DEINE-IP>.nip.io` (HTTP→HTTPS leitet
Caddy automatisch um). Der einfache Port-8080-Modus aus Schritt 4 wird dann nicht
mehr gebraucht.

> Schlägt die Zertifikatsausstellung fehl (nip.io teilt sich ein Let's-Encrypt-
> Rate-Limit): **`sslip.io`** ist ein 1:1-Ersatz — `SITE_ADDRESS` auf
> `…<DEINE-IP>.sslip.io` umstellen. Häufigste andere Ursache: Port 80 nicht erreichbar.

## Betrieb

| Aktion | Befehl |
|---|---|
| Logs ansehen | `sudo docker compose logs -f` |
| Status / Health | `sudo docker compose ps` |
| Aktualisieren | `sudo docker compose pull && sudo docker compose up -d` |
| Stoppen | `sudo docker compose down` |
| Neu starten | `sudo docker compose restart` |

Durch `restart: unless-stopped` + aktivierten Docker-Dienst startet der
Container nach einem Server-Neustart automatisch wieder.

## Hinweise

- **Datenstand:** Das Image enthält `truth.json`. Der Live-Refresh (Team-Button)
  baut die Daten im Container neu, aber **nur bis zum Neustart** (ephemer). Für
  dauerhaft frische Daten das Image regelmäßig neu ziehen (CI baut es bei jedem
  Push auf `main` neu).
- **HTTPS:** Für öffentlichen Betrieb einen Reverse-Proxy (Caddy/nginx/Traefik)
  vor den Container setzen, der TLS terminiert und auf `127.0.0.1:8080` weiterleitet
  (Schritt 5 erledigt das mit Caddy automatisch).
- **Kein Passwort-Default:** Ohne gesetztes `QE_TEAM_PASSWORD` sind die Team-Funktionen
  deaktiviert (fail closed); ohne `QE_TIER1_PASSWORD` ist Tier 1 (Details) offen.
- **Nächtlicher Auto-Refresh (optional):** `QE_AUTO_REFRESH_HOUR=3` baut die Daten
  täglich um 03:00 Uhr neu (leer = aus). Der Refresh-Button selbst ist team-geschützt.
