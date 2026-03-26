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
npm run check            # TypeScript-Check
npx drizzle-kit push     # DB-Migration

# Docker
docker compose up -d     # Container starten (Port 3001)
docker compose logs -f   # Logs
```

