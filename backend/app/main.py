from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import projects, uploads, extraction, tasks, matching

# Import models so they're registered with Base before create_all
import app.models  # noqa: F401

# Create tables on startup (idempotent)
init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="AKS Export API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(extraction.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(matching.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
