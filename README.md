# AKS Export — BIM-Automatisierung

Web-Anwendung zur automatisierten Extraktion von AKS-Kennzeichnungen aus PDF-Plaenen und zum Abgleich mit Revit-Elementen. Ergebnis: fertige Revit-Import-Excel-Dateien.

## Workflow

1. **Projekt erstellen** — Projektcode, AKS-Regex und Geraete-Typ-Mapping konfigurieren
2. **PDFs hochladen** — Schema- und Grundriss-PDFs sowie Revit-Excel-Exporte
3. **AKS extrahieren** — Automatische Erkennung aus Schema- und Grundriss-Plaenen
4. **Matching** — Revit-Elemente den extrahierten AKS-Kennzeichnungen zuordnen
5. **Review** — Zuordnungen pruefen, korrigieren (Swap, Unmatch, Manual Match)
6. **Export** — Revit-Import-Excel mit korrigierten Zuordnungen herunterladen

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, SQLite, PyMuPDF
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query
- **Infrastruktur:** Docker, Nginx, GitHub Actions (GHCR)

## Setup

### Voraussetzungen

- Docker und Docker Compose
- (Fuer Entwicklung: Python 3.12+, Node.js 20+)

### Mit Docker starten

```bash
# Repository klonen
git clone https://github.com/Silverback42/AKS_Export.git
cd AKS_Export

# Umgebungsvariablen konfigurieren
cp .env.example .env

# Container starten
docker compose up --build
```

Die Anwendung ist dann erreichbar unter:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000/docs

### Entwicklung (ohne Docker)

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Der Vite-Dev-Server laeuft auf http://localhost:5173 und leitet `/api`-Anfragen an das Backend weiter.

## Konfiguration

Siehe [.env.example](.env.example) fuer alle verfuegbaren Umgebungsvariablen:

| Variable | Beschreibung | Standard |
|---|---|---|
| `DATABASE_URL` | SQLite-Datenbankpfad | `sqlite:///./data/aks_export.db` |
| `DATA_DIR` | Verzeichnis fuer Uploads und Exports | `./data` |
| `CORS_ORIGINS` | Erlaubte CORS-Origins (JSON-Array) | `["http://localhost:3000","http://localhost:5173"]` |
| `MAX_UPLOAD_SIZE` | Max. Upload-Groesse in Bytes | `104857600` (100 MB) |

## Projektstruktur

```
aks-export-app/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI App + CORS + Lifespan
│   │   ├── config.py          # Pydantic BaseSettings
│   │   ├── database.py        # SQLAlchemy Engine + Session
│   │   ├── models.py          # ORM Models
│   │   ├── schemas.py         # Request/Response Schemas
│   │   ├── routers/           # API-Endpoints
│   │   ├── services/          # Business-Logik
│   │   └── core/tools/        # Extraktions- und Matching-Tools
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/client.ts      # API-Client (Axios)
│   │   ├── pages/             # Seiten-Komponenten
│   │   ├── components/        # UI-Komponenten
│   │   ├── stores/            # Zustand Stores
│   │   └── types/             # TypeScript Interfaces
│   └── Dockerfile
├── docker-compose.yml
└── .env.example
```

## API

Die vollstaendige API-Dokumentation ist ueber Swagger UI erreichbar: http://localhost:8000/docs

## Lizenz

Proprietaer — Alle Rechte vorbehalten.
