# Projektplan: AKS Export Web Application

---

## Phase 1: Foundation

### 1.1 Backend-Grundgeruest
- [x] Monorepo-Struktur anlegen (`aks-export-app/backend/`, `frontend/`)
- [x] `requirements.txt` mit allen Backend-Dependencies
- [x] FastAPI App erstellen (`app/main.py`) mit CORS + Lifespan
- [x] Pydantic BaseSettings (`app/config.py`)
- [x] SQLite + SQLAlchemy Setup (`app/database.py`)
- [x] ORM Models definieren (`app/models.py`): Project, Upload, Task, MatchCorrection
- [x] Pydantic Schemas (`app/schemas.py`): Request/Response fuer alle Endpoints
- [x] Alembic fuer DB-Migrationen einrichten

### 1.2 Projekt-CRUD API
- [x] `GET /api/projects` — Alle Projekte auflisten
- [x] `POST /api/projects` — Neues Projekt erstellen (Name, Code, Config)
- [x] `GET /api/projects/{id}` — Projekt-Details + Status
- [x] `PUT /api/projects/{id}` — Projekt-Config aktualisieren
- [x] `DELETE /api/projects/{id}` — Projekt + Daten loeschen

### 1.3 Datei-Upload API
- [x] `POST /api/projects/{id}/uploads` — Multipart File-Upload mit Streaming
- [x] `GET /api/projects/{id}/uploads` — Uploads auflisten
- [x] `DELETE /api/projects/{id}/uploads/{uid}` — Upload loeschen
- [x] Dateityp-Erkennung (Schema-PDF, Grundriss-PDF, Revit-Excel)
- [x] Dateispeicherung unter `data/projects/{project_id}/uploads/`

### 1.4 Docker-Setup
- [x] Backend `Dockerfile` (Python 3.12-slim + PyMuPDF)
- [x] Frontend `Dockerfile` (multi-stage: Node Build + Nginx)
- [x] `docker-compose.yml` mit Volume fuer persistente Daten
- [x] `nginx.conf` mit API-Proxy (`/api/*` -> Backend)
- [ ] `docker compose up --build` laeuft fehlerfrei (Docker Desktop nicht verfuegbar)

### 1.5 Frontend-Grundgeruest
- [x] Vite + React + TypeScript Projekt initialisieren
- [x] Tailwind CSS einrichten
- [x] shadcn/ui installieren und konfigurieren
- [x] React Router v6 Setup mit Route-Struktur
- [x] Axios API-Client (`src/api/client.ts`)
- [x] AppShell-Layout (Navigation, Sidebar, Breadcrumbs)
- [x] TypeScript Interfaces (`src/types/`)

### 1.6 Projekt-UI
- [x] `ProjectListPage` — Projekt-Karten mit Name, Code, Status
- [x] "Neues Projekt"-Button + Erstellungs-Dialog
- [x] `ProjectForm` — Formular fuer Name, Projektcode, AKS-Regex, Raum-Config, Geraet-Type-Map
- [x] Projekt-Detail-Seite mit Uebersicht

### 1.7 Phase 1 Milestone
- [x] **TEST**: Projekt erstellen, Dateien hochladen, in UI sehen (via API-Tests verifiziert)
- [ ] **TEST**: Docker Compose startet Backend + Frontend fehlerfrei (Docker Desktop nicht verfuegbar)

---

## Phase 2: Extraktion (Schritt 1)

### 2.1 Tool-Integration
- [ ] Bestehende Python-Tools nach `app/core/tools/` kopieren
- [ ] `extract_schema_aks.py` refactoren: AKS-Regex als Parameter (statt hardcoded `WUN005`)
- [ ] `extract_grundriss_aks.py` refactoren: AKS-Regex als Parameter (Zeile ~76 + ~90)
- [ ] Alle Tools importierbar machen (relative Imports pruefen, `__init__.py`)

### 2.2 Background-Task-System
- [ ] `ThreadPoolExecutor` Setup (`app/tasks/background.py`, max 3 Worker)
- [ ] Task-Lifecycle: pending -> running -> completed/failed
- [ ] Fortschritts-Updates (progress 0-100) waehrend Ausfuehrung
- [ ] `GET /api/tasks/{task_id}` — Task-Status-Endpoint fuer Polling

### 2.3 Extraktions-Service
- [ ] `extraction_service.py` — Wrapper fuer Tool-Funktionen
- [ ] Schema-Extraktion mit Projekt-Config (Regex, Room-Pattern)
- [ ] Grundriss-Extraktion mit Projekt-Config
- [ ] Registry-Builder (Schema + Grundriss zusammenfuehren)
- [ ] Ergebnis-JSON unter `data/projects/{id}/intermediate/` speichern

### 2.4 Extraktions-API
- [ ] `POST /api/projects/{id}/extract/schema` — Schema-AKS extrahieren (-> task_id)
- [ ] `POST /api/projects/{id}/extract/grundriss` — Grundriss-AKS extrahieren (-> task_id)
- [ ] `POST /api/projects/{id}/registry/build` — AKS-Registry zusammenfuehren (-> task_id)
- [ ] `GET /api/projects/{id}/registry` — Registry-Daten + Summary abrufen
- [ ] `GET /api/projects/{id}/tasks` — Alle Tasks eines Projekts

### 2.5 Extraktions-UI (ExtractionPage)
- [ ] FileDropzone fuer PDF-Upload (Drag & Drop, react-dropzone)
- [ ] Automatische Dateityp-Erkennung mit manuellem Override-Dropdown
- [ ] Hochgeladene Dateien als Liste anzeigen (mit Loeschen-Button)
- [ ] "Extraktion starten"-Button
- [ ] Pipeline-Status-Anzeige (Schema -> Grundriss -> Registry) mit Fortschrittsbalken
- [ ] Task-Polling (alle 1-2 Sek.) mit usePolling Hook
- [ ] AKS-Registry-Summary nach Abschluss (Anzahl Equipment, Raeume, Gewerke)

### 2.6 AKS-Excel-Export
- [ ] `POST /api/projects/{id}/export/aks-registry` — AKS-Excel generieren
- [ ] `GET /api/projects/{id}/export/{tid}/download` — Excel herunterladen
- [ ] Download-Button in ExtractionPage

### 2.7 Phase 2 Milestone
- [ ] **TEST**: Schema-PDF hochladen -> Extraktion -> 490 AKS erwartet
- [ ] **TEST**: Grundriss-PDF hochladen -> Extraktion -> 68 AKS + 22 Querverweise
- [ ] **TEST**: Registry bauen -> Summary korrekt angezeigt
- [ ] **TEST**: AKS-Excel herunterladen und Inhalt pruefen

---

## Phase 3: Matching (Schritt 2)

### 3.1 Matching-Service
- [ ] `matching_service.py` — Wrapper fuer `parse_revit_export` + `match_revit_to_aks`
- [ ] Revit-Excel parsen mit Equipment-Type-Label
- [ ] Matching ausfuehren mit Equipment-Filter
- [ ] Ergebnisse unter `data/projects/{id}/intermediate/` speichern

### 3.2 Matching-API
- [ ] `POST /api/projects/{id}/revit/parse` — Revit-Excel parsen (-> task_id)
- [ ] `POST /api/projects/{id}/match` — Matching ausfuehren (-> task_id)
- [ ] `GET /api/projects/{id}/match/{tid}/results` — Match-Ergebnisse abrufen

### 3.3 Matching-UI (MatchingPage)
- [ ] FileDropzone fuer Revit-Excel-Upload
- [ ] Equipment-Typ-Dropdown (aus Projekt-Config: Leuchte, Motor/Ventil, Sensor etc.)
- [ ] "Matching starten"-Button mit Fortschrittsanzeige
- [ ] Raum-Uebersicht nach Abschluss:
  - [ ] GRUEN: Alle Matches HIGH Confidence
  - [ ] GELB: MEDIUM Confidence vorhanden
  - [ ] ROT: COUNT_MISMATCH oder fehlende Elemente
- [ ] Statistik-Summary (X matched, Y unmatched, Z rooms)

### 3.4 Quick-Export
- [ ] `POST /api/projects/{id}/export/revit-import` — Revit-Import-Excel generieren
- [ ] "Excel herunterladen"-Button (ohne Review)
- [ ] "Matches ueberpruefen"-Button (fuehrt zu ReviewPage)

### 3.5 Phase 3 Milestone
- [ ] **TEST**: `Leuchtenliste.xlsx` hochladen, Filter "Leuchte", 16 Matches (HIGH)
- [ ] **TEST**: Raum-Uebersicht zeigt korrekte Farbcodierung
- [ ] **TEST**: Quick-Export Excel herunterladen, 4 Sheets pruefen

---

## Phase 4: Match Review UI (Schritt 2b)

### 4.1 Review-Backend
- [ ] `GET /api/projects/{id}/match/{tid}/review` — Review-Daten laden (Matches + Unmatched)
- [ ] `POST /api/projects/{id}/match/{tid}/corrections` — Korrekturen speichern
- [ ] `GET /api/projects/{id}/match/{tid}/corrections` — Gespeicherte Korrekturen laden
- [ ] `DELETE /api/projects/{id}/match/{tid}/corrections/{cid}` — Korrektur entfernen
- [ ] `POST /api/projects/{id}/match/{tid}/apply-corrections` — Korrekturen auf Match-Ergebnis anwenden
- [ ] `export_results.py` erweitern: Korrekturen vor Excel-Generierung anwenden

### 4.2 Review-State (Zustand Store)
- [ ] `reviewStore.ts` — Matches, Korrekturen, Unmatched-Listen
- [ ] `swapMatches(id1, id2)` — AKS-Zuordnung zwischen zwei Zeilen tauschen
- [ ] `unmatchEntry(id)` — AKS von Revit-Element loesen
- [ ] `manualMatch(aksId, revitGuid)` — Manuell paaren
- [ ] `undoCorrection()` / `redoCorrection()` — Undo/Redo-Stack
- [ ] `resetAllCorrections()` — Alle Korrekturen zuruecksetzen
- [ ] `saveCorrections()` — POST an API

### 4.3 Review-Tabelle (MatchReviewTable)
- [ ] TanStack Table v8 Setup mit sortierbaren Spalten
- [ ] Raum-Gruppierung mit einklappbaren Sektionen
- [ ] Spalten: Raum, AKS, Geraet, Revit GUID, Revit Type, Confidence, Aktionen
- [ ] `ConfidenceBadge` Komponente (GRUEN/GELB/ROT/BLAU)
- [ ] Zeilen-Highlighting fuer korrigierte Matches (blauer Rand)

### 4.4 Interaktionen
- [ ] **Swap**: "Tauschen"-Button -> Klick auf zweite Zeile im selben Raum -> AKS getauscht
- [ ] **Unmatch**: "Loesen"-Button -> AKS + Revit-Element wandern in Unmatched-Panels
- [ ] **Manual Match (Click-to-Pair)**: Klick auf ungematchtes AKS, dann Klick auf ungematchtes Revit-Element
- [ ] **Manual Match (Drag & Drop)**: AKS aus Sidebar auf Revit-Zeile ziehen
- [ ] Visuelles Feedback bei Hover/Drag (Drop-Target hervorheben)

### 4.5 Unmatched-Panel (Sidebar)
- [ ] Rechte Sidebar (einklappbar)
- [ ] "Unmatched AKS"-Liste (AKS ohne Revit-Zuordnung)
- [ ] "Unmatched Revit"-Liste (Revit-Elemente ohne AKS)
- [ ] Drag-fuer-Pairing oder Click-to-Pair

### 4.6 Filter und Navigation
- [ ] Filter: Alle anzeigen / Nur Probleme (MEDIUM + LOW) / Nur korrigierte
- [ ] Raum-Schnellnavigation (Klick auf Raum in Summary -> Scroll zu Raum)
- [ ] Zaehler in Topbar: "X Korrekturen vorgenommen"

### 4.7 Speichern und Export
- [ ] "Korrekturen speichern"-Button -> POST an API
- [ ] "Export mit Korrekturen"-Button -> Korrigiertes Revit-Import-Excel
- [ ] Warnung bei ungespeicherten Korrekturen (Browser-Leave-Guard)

### 4.8 Phase 4 Milestone
- [ ] **TEST**: Review-Seite oeffnen, alle Matches nach Raum gruppiert sichtbar
- [ ] **TEST**: Swap zwischen zwei Leuchten im selben Raum funktioniert
- [ ] **TEST**: Unmatch -> Element erscheint in Sidebar
- [ ] **TEST**: Manual Match aus Sidebar -> neues Paar erstellt
- [ ] **TEST**: Undo/Redo fuer alle Korrektur-Typen
- [ ] **TEST**: Korrekturen speichern -> Export -> Excel enthaelt korrigierte Zuordnungen

---

## Phase 5: Polish

### 5.1 Fehlerbehandlung
- [ ] API-Fehler-Responses mit klaren Meldungen
- [ ] Frontend Error Boundaries
- [ ] Toast-Benachrichtigungen (Erfolg, Fehler, Warnung)
- [ ] Validierung bei Projekt-Erstellung (Pflichtfelder, Regex-Syntax)

### 5.2 UX-Verbesserungen
- [ ] Loading States fuer alle async Operationen
- [ ] Empty States (kein Projekt, keine Uploads, keine Matches)
- [ ] Responsive Layout-Anpassungen
- [ ] Tastatur-Shortcuts fuer Review (Undo: Ctrl+Z, Redo: Ctrl+Y)

### 5.3 Erweiterte Features
- [ ] Task-Retry: Fehlgeschlagene Extraktion/Matching erneut starten
- [ ] "Registry wiederverwenden": Schritt 2 ohne erneuten PDF-Upload
- [ ] Projekt-Loeschung mit Bestaetigungs-Dialog
- [ ] Mehrere Grundriss-PDFs pro Projekt unterstuetzen

### 5.4 Deployment und Dokumentation
- [ ] Docker Compose Endtest auf sauberem System
- [ ] `.env.example` mit Dokumentation
- [ ] README mit Setup-Anleitung und Screenshots

### 5.5 Phase 5 Milestone
- [ ] **TEST**: `docker compose up --build` auf sauberem System -> App laeuft
- [ ] **TEST**: Kompletter Workflow durchspielen (Projekt -> Upload -> Extraktion -> Matching -> Review -> Export)
- [ ] **TEST**: Multi-Projekt: Zweites Projekt mit anderem Code erstellen und durchspielen
- [ ] **TEST**: Fehlerfaelle pruefen (ungueltige PDF, leere Excel, fehlende Uploads)

---

## Fortschritt

| Phase | Status | Tasks gesamt | Erledigt |
|---|---|---|---|
| Phase 1: Foundation | Fast fertig | 30 | 28 |
| Phase 2: Extraktion | Offen | 25 | 0 |
| Phase 3: Matching | Offen | 14 | 0 |
| Phase 4: Match Review | Offen | 27 | 0 |
| Phase 5: Polish | Offen | 15 | 0 |
| **Gesamt** | | **111** | **28** |
