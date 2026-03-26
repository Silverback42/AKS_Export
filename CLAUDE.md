# Globale Entwickler-Präferenzen

## Allgemeine Regeln
- Bevorzuge TypeScript über JavaScript
- Schreibe Code auf Englisch, Kommentare auf Deutsch
- Verwende moderne ES6+ Syntax
- Keine console.log() in Production-Code

## Code-Qualität
- Schreibe sauberen, lesbaren Code
- Verwende aussagekräftige Variablennamen
- Halte Funktionen klein (max. 20 Zeilen)
- DRY-Prinzip befolgen

## Fehlerbehandlung
- Immer try-catch bei async/await
- Niemals Fehler verschlucken
- Aussagekräftige Fehlermeldungen

## Git
- Commit-Messages auf Deutsch
- Conventional Commits Format nutzen
- Niemals direkt auf main pushen

## Testen
- Teste immer wenn möglich

---

# Vermögenstracker PWA

## Projektbeschreibung
Progressive Web App zur Verfolgung des persönlichen Nettovermögens über Zeit.
Läuft als Docker Container (Port 3001) auf Synology NAS, installierbar auf Android via Homescreen.
Design orientiert sich an der **Finanzfluss Copilot App** und dem Haushaltsbuch-Projekt.

## Tech Stack
- **Frontend**: SvelteKit (SSR + PWA)
- **Styling**: Tailwind CSS 4 (Mobile-first, Dark Mode als Standard)
- **Backend**: SvelteKit Server Routes (API)
- **Datenbank**: SQLite via `better-sqlite3`
- **ORM**: Drizzle ORM
- **Charts**: Chart.js (direkt, kein svelte-chartjs Wrapper)
- **Docker**: Single Container (Node 20 Alpine, Port 3001)
- **PWA**: Web Manifest + Service Worker

## Architektur
```
Docker Container (Port 3001)
├── SvelteKit App (SSR + API Routes)
└── SQLite DB (/data/vermoegenstracker.db)
    └── Docker Volume: ./data
```

## Projektstruktur
```
vermoegenstracker/
├── src/
│   ├── lib/
│   │   ├── server/          # DB-Verbindung, Schema, Seed-Daten
│   │   ├── components/      # Svelte UI-Komponenten
│   │   ├── utils/           # Formatierung, Hilfsfunktionen
│   │   └── types.ts         # TypeScript Interfaces und Konstanten
│   └── routes/
│       ├── +page.svelte           # Dashboard (Nettovermögen-Timeline)
│       ├── assets/                # Anlage-Verwaltung (Add/Toggle/Delete)
│       ├── snapshot/[month]/      # Monatliche Snapshot-Eingabe (Autosave)
│       ├── statistik/             # Jahres-Charts, Best/Worst, Wachstum
│       └── einstellungen/         # CSV Import/Export
```

## Design-System (Finanzfluss Copilot Style)
- Identisch mit dem Haushaltsbuch-Projekt
- Dark Mode als Standard, Farben via CSS `@theme` in `app.css`
- bg `#0f1729`, cards `#1e2a3a`, primary `#3b82f6`
- Asset-Typen: bank `#3b82f6`, depot `#22c55e`, crypto `#f97316`, real_estate `#a855f7`, liability `#ef4444`

## Datenbank

### assets
- id, name, type (bank/depot/crypto/real_estate/liability), description, sort_order, is_active, created_at

### snapshots
- id, asset_id (FK → assets), year, month, value (positiv=Asset, negativ=Verbindlichkeit), note, created_at
- UNIQUE(asset_id, year, month)

### settings
- key (PK), value

## Befehle
```bash
# Entwicklung (im Ordner vermoegenstracker/)
npm run dev              # Dev-Server (Port 5173)
npm run build            # Produktions-Build
npm run check            # TypeScript-Check
npx drizzle-kit push     # DB-Migration

# Docker
docker compose up -d     # Container starten (Port 3001)
docker compose logs -f   # Logs
```

