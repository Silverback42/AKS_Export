"""Extraction API endpoints — Schema, Grundriss, Registry build + AKS Excel export."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Project, Task, Upload
from app.schemas import TaskResponse, RegistrySummaryResponse
from app.tasks.background import run_in_background
from app.services.extraction_service import (
    run_schema_extraction,
    run_grundriss_extraction,
    run_registry_build,
    run_aks_excel_export,
)

router = APIRouter(tags=["extraction"])


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _find_upload_by_type(project_id: str, file_type: str, db: Session) -> Upload:
    """Finde den neuesten Upload eines bestimmten Typs."""
    upload = (
        db.query(Upload)
        .filter(Upload.project_id == project_id, Upload.file_type == file_type)
        .order_by(Upload.created_at.desc())
        .first()
    )
    if not upload:
        raise HTTPException(
            status_code=400,
            detail=f"Kein Upload vom Typ '{file_type}' gefunden. Bitte zuerst hochladen.",
        )
    return upload


def _create_task(project_id: str, task_type: str, db: Session) -> Task:
    task = Task(project_id=project_id, task_type=task_type, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/projects/{project_id}/extract/schema", response_model=TaskResponse)
def extract_schema(project_id: str, db: Session = Depends(get_db)):
    """Schema-AKS aus hochgeladenem Schema-PDF extrahieren."""
    project = _get_project_or_404(project_id, db)
    upload = _find_upload_by_type(project_id, "schema_pdf", db)

    pdf_path = Path(settings.data_dir) / upload.file_path
    if not pdf_path.exists():
        raise HTTPException(status_code=400, detail="Upload-Datei nicht gefunden auf Disk")

    task = _create_task(project_id, "extract_schema", db)

    # AKS-Regex fuer Extraktion zusammenbauen
    aks_regex = project.aks_regex + r"[xX]?_\w+(?:_\w+){4,6}"

    run_in_background(
        task.id,
        run_schema_extraction,
        project_id=project_id,
        pdf_path=str(pdf_path),
        aks_regex=aks_regex,
        room_code_pattern=project.room_code_pattern,
        room_format=project.room_format,
    )

    return TaskResponse.model_validate(task)


@router.post("/projects/{project_id}/extract/grundriss", response_model=TaskResponse)
def extract_grundriss(project_id: str, db: Session = Depends(get_db)):
    """Grundriss-AKS aus hochgeladenem Grundriss-PDF extrahieren."""
    project = _get_project_or_404(project_id, db)
    upload = _find_upload_by_type(project_id, "grundriss_pdf", db)

    pdf_path = Path(settings.data_dir) / upload.file_path
    if not pdf_path.exists():
        raise HTTPException(status_code=400, detail="Upload-Datei nicht gefunden auf Disk")

    task = _create_task(project_id, "extract_grundriss", db)

    aks_regex = project.aks_regex + r"[xX]?_\w+(?:_\w+)*"

    run_in_background(
        task.id,
        run_grundriss_extraction,
        project_id=project_id,
        pdf_path=str(pdf_path),
        aks_regex=aks_regex,
        room_code_pattern=project.room_code_pattern,
        room_format=project.room_format,
        geraet_type_map=project.get_geraet_type_map(),
    )

    return TaskResponse.model_validate(task)


@router.post("/projects/{project_id}/registry/build", response_model=TaskResponse)
def build_registry(project_id: str, db: Session = Depends(get_db)):
    """Schema + Grundriss zu AKS-Registry zusammenfuehren."""
    _get_project_or_404(project_id, db)

    task = _create_task(project_id, "build_registry", db)

    run_in_background(
        task.id,
        run_registry_build,
        project_id=project_id,
    )

    return TaskResponse.model_validate(task)


@router.get("/projects/{project_id}/registry", response_model=RegistrySummaryResponse)
def get_registry(project_id: str, db: Session = Depends(get_db)):
    """Registry-Daten + Summary abrufen."""
    _get_project_or_404(project_id, db)

    registry_path = Path(settings.data_dir) / "projects" / project_id / "intermediate" / "aks_registry.json"
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry nicht vorhanden. Bitte zuerst bauen.")

    import json
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)

    return RegistrySummaryResponse(
        metadata=data["metadata"],
        room_index=data.get("room_index", {}),
        equipment_count=data["metadata"]["total_equipment"],
        schema_aks_count=data["metadata"]["total_schema_aks"],
        cross_ref_count=data["metadata"]["total_cross_refs"],
    )


@router.post("/projects/{project_id}/export/aks-registry", response_model=TaskResponse)
def export_aks_registry(project_id: str, db: Session = Depends(get_db)):
    """AKS-Registry als Excel exportieren."""
    _get_project_or_404(project_id, db)

    task = _create_task(project_id, "export_aks_excel", db)

    run_in_background(
        task.id,
        run_aks_excel_export,
        project_id=project_id,
    )

    return TaskResponse.model_validate(task)


@router.get("/projects/{project_id}/export/{task_id}/download")
def download_export(project_id: str, task_id: str, db: Session = Depends(get_db)):
    """Exportierte Excel-Datei herunterladen."""
    _get_project_or_404(project_id, db)

    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task nicht gefunden")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail=f"Task noch nicht fertig (Status: {task.status})")
    if not task.result_path:
        raise HTTPException(status_code=400, detail="Kein Ergebnis vorhanden")

    file_path = Path(task.result_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export-Datei nicht gefunden")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
