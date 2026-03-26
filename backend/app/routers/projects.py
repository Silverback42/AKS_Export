import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Project
from app.schemas import (
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdateRequest,
    UploadResponse,
)
from app.core.tools.aks_structure import DEFAULT_GERAET_TYPE_MAP


def _build_aks_regex(project_code: str) -> str:
    """Baut AKS-Regex aus Liegenschaftskuerzel: WUN -> WUN\\d{3}[xX]?"""
    return rf"{re.escape(project_code)}\d{{3}}[xX]?"

router = APIRouter(tags=["projects"])


def _project_to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        project_code=project.project_code,
        aks_regex=project.aks_regex,
        room_code_pattern=project.room_code_pattern,
        room_format=project.room_format,
        geraet_type_map=project.get_geraet_type_map(),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    items = []
    for p in projects:
        items.append(ProjectListItem(
            id=p.id,
            name=p.name,
            project_code=p.project_code,
            created_at=p.created_at,
            updated_at=p.updated_at,
            upload_count=len(p.uploads),
        ))
    return ProjectListResponse(projects=items)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(req: ProjectCreateRequest, db: Session = Depends(get_db)):
    # Check unique project_code
    existing = db.query(Project).filter(Project.project_code == req.project_code).first()
    if existing:
        raise HTTPException(status_code=409, detail="Project code already exists")

    project = Project(
        name=req.name,
        project_code=req.project_code,
        aks_regex=_build_aks_regex(req.project_code),
        room_code_pattern=r"(EG|KG|OG|DA)(\d{3})",
        room_format="{0}.{1}",
    )
    project.set_geraet_type_map(DEFAULT_GERAET_TYPE_MAP)

    db.add(project)
    db.commit()
    db.refresh(project)

    # Create project data directory
    project_dir = Path(settings.data_dir) / "projects" / project.id / "uploads"
    project_dir.mkdir(parents=True, exist_ok=True)

    return _project_to_response(project)


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = _get_project_or_404(project_id, db)
    resp = ProjectDetailResponse(
        **_project_to_response(project).model_dump(),
        uploads=[UploadResponse.model_validate(u) for u in project.uploads],
    )
    return resp


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, req: ProjectUpdateRequest, db: Session = Depends(get_db)):
    project = _get_project_or_404(project_id, db)

    if req.name is not None:
        project.name = req.name
    if req.project_code is not None:
        existing = db.query(Project).filter(
            Project.project_code == req.project_code,
            Project.id != project_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Project code already exists")
        project.project_code = req.project_code
        project.aks_regex = _build_aks_regex(req.project_code)

    db.commit()
    db.refresh(project)
    return _project_to_response(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = _get_project_or_404(project_id, db)

    # Delete project files from disk
    project_dir = Path(settings.data_dir) / "projects" / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    db.delete(project)
    db.commit()
