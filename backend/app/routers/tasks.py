"""Task status API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, Task
from app.schemas import TaskResponse, TaskListResponse

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Task-Status abfragen (fuer Polling)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task nicht gefunden")
    return TaskResponse.model_validate(task)


@router.get("/projects/{project_id}/tasks", response_model=TaskListResponse)
def list_project_tasks(project_id: str, db: Session = Depends(get_db)):
    """Alle Tasks eines Projekts auflisten."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = (
        db.query(Task)
        .filter(Task.project_id == project_id)
        .order_by(Task.created_at.desc())
        .all()
    )
    return TaskListResponse(tasks=[TaskResponse.model_validate(t) for t in tasks])
