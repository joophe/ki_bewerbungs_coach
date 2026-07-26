# Deployment: KI Bewerbungs Coach als Web-Demo

Diese Anleitung stellt den Coach als **Browser-Terminal** auf einem Linux-VPS
(z. B. netcup) bereit, erreichbar über eine eigene Domain (DNS z. B. bei Strato)
mit automatischem HTTPS. Als Modell wird ein **kostenloses OpenRouter-Modell**
genutzt, sodass keine laufenden API-Kosten entstehen.

```
Browser ──HTTPS──▶ Caddy (VPS) ──▶ App (FastAPI + PTY) ──▶ python -m ki_bewerbungs_coach ──▶ OpenRouter (:free)
```

## Wie es funktioniert

Die bestehende interaktive CLI wird **nicht umgeschrieben**. Der Web-Server
startet sie pro Browser-Sitzung in einer Pseudo-TTY (PTY) und verbindet sie über
WebSocket mit einem Terminal (xterm.js) im Browser. So bleibt die gesamte
`rich`-Oberfläche erhalten und fühlt sich an wie im echten Terminal.

Aus Sicherheitsgründen wird ausschließlich das feste Coach-Modul gestartet –
**keine Shell**. Besucher können also keine beliebigen Befehle ausführen.

---

## 1. Voraussetzungen

- Ein Linux-VPS (netcup) mit öffentlicher IPv4/IPv6 und Root/sudo-Zugang.
- Eine (Sub-)Domain, deren DNS du verwaltest (Strato).
- Ein kostenloser **OpenRouter**-Account und API-Key: <https://openrouter.ai/keys>
  - Tipp: **keine Zahlungsmethode hinterlegen** – dann sind ausschließlich
    `:free`-Modelle nutzbar und es kann garantiert nichts abgerechnet werden.

## 2. DNS bei Strato setzen

Lege im Strato-DNS-Verwaltungsbereich einen Eintrag an, der auf die VPS-IP zeigt:

| Typ | Name (Host)            | Wert (Ziel)      |
|-----|------------------------|------------------|
| A   | `coach` (oder `@`)     | `<VPS-IPv4>`     |
| AAAA| `coach` (optional)     | `<VPS-IPv6>`     |

Ergebnis z. B.: `coach.deine-domain.de`. Die Verbreitung kann einige Minuten bis
Stunden dauern. Prüfen: `dig +short coach.deine-domain.de` muss die VPS-IP zeigen.

> Strato dient hier nur als DNS/Domain. Die Anwendung läuft vollständig auf dem VPS.

## 3. VPS vorbereiten (Docker installieren)

```bash
# Als root oder mit sudo
curl -fsSL https://get.docker.com | sh
# Firewall: Ports 80 und 443 öffnen (Beispiel ufw)
ufw allow 80/tcp && ufw allow 443/tcp
```

## 4. Code holen und Branch auschecken

```bash
git clone https://github.com/joophe/ki_bewerbungs_coach.git
cd ki_bewerbungs_coach
git checkout feature/web-terminal
```

## 5. Konfiguration (`.env`)

```bash
cp .env.example .env
nano .env
```

Mindestens setzen (alles andere kann Standard bleiben):

```dotenv
# Modell über OpenRouter (kostenlos, keine Kostenfalle)
MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-...

# Domain für automatisches HTTPS
SITE_ADDRESS=coach.deine-domain.de

# optionale Grenzen der öffentlichen Demo
WEB_MAX_SESSIONS=5
WEB_IDLE_TIMEOUT_SECONDS=300
WEB_MAX_SESSION_SECONDS=1800
```

> Ein aktuelles Gratis-Modell auswählen: <https://openrouter.ai/models?max_price=0>.
> Gute Kandidaten sind meist ein Llama-3.3-70B- oder DeepSeek-`:free`-Modell.
> Die `.env` ist per `.gitignore`/`.dockerignore` ausgeschlossen und landet
> weder im Git noch im Image.

## 6. Starten

```bash
docker compose up -d --build
```

Caddy holt beim ersten Start automatisch ein Let's-Encrypt-Zertifikat für
`SITE_ADDRESS`. Danach ist die Demo erreichbar unter:

```
https://coach.deine-domain.de
```

Nützliche Befehle:

```bash
docker compose logs -f          # Logs verfolgen
docker compose ps               # Status
docker compose down             # stoppen
docker compose up -d --build    # nach Änderungen neu bauen
```

## 7. Lokaler Test ohne Domain (optional)

Nur HTTP, ohne TLS – praktisch zum Ausprobieren:

```bash
echo "SITE_ADDRESS=:80" >> .env   # statt der Domain
docker compose up --build
# Browser: http://<VPS-IP>  bzw.  http://localhost
```

---

## Betrieb, Kosten & Sicherheit

- **Keine Kostenfalle:** Mit einem `:free`-Modell und ohne hinterlegte
  Zahlungsmethode bei OpenRouter entstehen keine API-Kosten. Bei zu vielen
  Anfragen greift lediglich das Rate-Limit von OpenRouter (der Coach hat für
  leere/limitierte Antworten bereits eine Fallback-Logik).
- **Ressourcenschutz:** `WEB_MAX_SESSIONS` begrenzt gleichzeitige Sitzungen,
  `WEB_IDLE_TIMEOUT_SECONDS` und `WEB_MAX_SESSION_SECONDS` beenden inaktive bzw.
  überlange Sitzungen automatisch.
- **Isolation:** Jede Sitzung läuft als eigener Kindprozess in einem eigenen
  temporären Verzeichnis (unter `/tmp`, als `tmpfs`), ohne persistente Daten.
  Der Container läuft als unprivilegierter Nutzer mit `no-new-privileges`.
- **Datenschutz / EU AI Act:** Die Seite weist sichtbar darauf hin, dass Nutzer
  mit einem KI-System interagieren und keine vertraulichen/unnötigen
  personenbezogenen Daten eingeben sollen. Eingaben werden zur Generierung an
  den externen Modellanbieter (OpenRouter) übertragen. Es werden serverseitig
  keine Eingaben oder Ergebnisse gespeichert.

## Optionale Härtung

- Zugangsschutz (z. B. Basic-Auth in Caddy) ergänzen, falls die Demo nicht
  vollständig offen sein soll:
  ```
  {$SITE_ADDRESS} {
      basic_auth {
          demo <bcrypt-hash>
      }
      reverse_proxy app:8000
  }
  ```
  Hash erzeugen: `docker run --rm caddy:2 caddy hash-password --plaintext 'geheim'`.
- Die xterm.js-Assets werden aktuell von einem CDN (jsDelivr, gepinnte Version)
  geladen. Für vollständige Unabhängigkeit können die Dateien lokal in
  `src/ki_bewerbungs_coach/web/static/` abgelegt und im HTML referenziert werden.
