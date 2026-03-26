"""Matching API endpoints — Revit parse, match, results, and export."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Project, Task, Upload
from app.schemas import TaskResponse, MatchRequest, RevitParseRequest, MatchResultsResponse
from app.tasks.background import run_in_background
from app.services.matching_service import (
    run_revit_parse,
    run_matching,
    run_revit_import_export,
)

router = APIRouter(tags=["matching"])


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _create_task(project_id: str, task_type: str, db: Session) -> Task:
    task = Task(project_id=project_id, task_type=task_type, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/projects/{project_id}/revit/parse", response_model=TaskResponse)
def parse_revit(
    project_id: str,
    req: RevitParseRequest = RevitParseRequest(),
    db: Session = Depends(get_db),
):
    """Revit-Excel parsen und als JSON speichern."""
    _get_project_or_404(project_id, db)

    # Neueste Revit-Excel finden
    upload = (
        db.query(Upload)
        .filter(Upload.project_id == project_id, Upload.file_type == "revit_excel")
        .order_by(Upload.created_at.desc())
        .first()
    )
    if not upload:
        raise HTTPException(status_code=400, detail="Keine Revit-Excel hochgeladen")

    excel_path = Path(settings.data_dir) / upload.file_path
    if not excel_path.exists():
        raise HTTPException(status_code=400, detail="Upload-Datei nicht gefunden auf Disk")

    task = _create_task(project_id, "parse_revit", db)

    run_in_background(
        task.id,
        run_revit_parse,
        project_id=project_id,
        excel_path=str(excel_path),
        equipment_type=req.equipment_type,
    )

    return TaskResponse.model_validate(task)


@router.post("/projects/{project_id}/match", response_model=TaskResponse)
def run_match(
    project_id: str,
    req: MatchRequest,
    db: Session = Depends(get_db),
):
    """Matching zwischen Revit-Elementen und AKS-Registry ausfuehren."""
    _get_project_or_404(project_id, db)

    task = _create_task(project_id, "match_revit", db)

    run_in_background(
        task.id,
        run_matching,
        project_id=project_id,
        equipment_filter=req.equipment_filter,
    )

    return TaskResponse.model_validate(task)


@router.get("/projects/{project_id}/match/{task_id}/results", response_model=MatchResultsResponse)
def get_match_results(project_id: str, task_id: str, db: Session = Depends(get_db)):
    """Match-Ergebnisse abrufen."""
    _get_project_or_404(project_id, db)

    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task nicht gefunden")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail=f"Task noch nicht fertig (Status: {task.status})")

    # Match-Ergebnisse aus intermediate laden
    match_path = Path(settings.data_dir) / "projects" / project_id / "intermediate" / "match_results.json"
    if not match_path.exists():
        raise HTTPException(status_code=404, detail="Match-Ergebnisse nicht gefunden")

    with open(match_path, encoding="utf-8") as f:
        data = json.load(f)

    return MatchResultsResponse(**data)


@router.post("/projects/{project_id}/export/revit-import", response_model=TaskResponse)
def export_revit_import(project_id: str, db: Session = Depends(get_db)):
    """Revit-Import-Excel mit AKS-Zuordnungen generieren."""
    _get_project_or_404(project_id, db)

    # Original-Excel finden fuer Reimport-Format
    upload = (
        db.query(Upload)
        .filter(Upload.project_id == project_id, Upload.file_type == "revit_excel")
        .order_by(Upload.created_at.desc())
        .first()
    )
    if not upload:
        raise HTTPException(status_code=400, detail="Keine Revit-Excel hochgeladen")

    excel_path = Path(settings.data_dir) / upload.file_path
    if not excel_path.exists():
        raise HTTPException(status_code=400, detail="Upload-Datei nicht gefunden auf Disk")

    task = _create_task(project_id, "export_revit_import", db)

    run_in_background(
        task.id,
        run_revit_import_export,
        project_id=project_id,
        original_excel_path=str(excel_path),
    )

    return TaskResponse.model_validate(task)
