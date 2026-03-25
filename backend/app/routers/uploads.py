import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Project, Upload
from app.schemas import UploadListResponse, UploadResponse

router = APIRouter(tags=["uploads"])


def _detect_file_type(filename: str) -> str:
    name_upper = filename.upper()
    ext = Path(filename).suffix.lower()

    if ext in (".xlsx", ".xls"):
        return "revit_excel"
    if ext == ".pdf":
        if "SCH" in name_upper or "SCHEMA" in name_upper:
            return "schema_pdf"
        if "G00" in name_upper or "GRUNDRISS" in name_upper:
            return "grundriss_pdf"
        return "schema_pdf"  # default for PDFs
    return "unknown"


@router.post(
    "/projects/{project_id}/uploads",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_file(
    project_id: str,
    file: UploadFile,
    file_type: str | None = None,
    db: Session = Depends(get_db),
):
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Determine file type
    detected_type = file_type or _detect_file_type(file.filename or "unknown")
    if detected_type not in ("schema_pdf", "grundriss_pdf", "revit_excel"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {detected_type}")

    # Create upload directory
    upload_dir = Path(settings.data_dir) / "projects" / project_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file to disk
    file_uuid = str(uuid4())
    safe_filename = f"{file_uuid}_{file.filename}"
    file_path = upload_dir / safe_filename

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = file_path.stat().st_size

    # Create DB record
    upload = Upload(
        project_id=project_id,
        filename=file.filename,
        file_type=detected_type,
        file_path=str(Path("projects") / project_id / "uploads" / safe_filename),
        file_size=file_size,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    return UploadResponse.model_validate(upload)


@router.get("/projects/{project_id}/uploads", response_model=UploadListResponse)
def list_uploads(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    uploads = (
        db.query(Upload)
        .filter(Upload.project_id == project_id)
        .order_by(Upload.created_at.desc())
        .all()
    )
    return UploadListResponse(
        uploads=[UploadResponse.model_validate(u) for u in uploads]
    )


@router.delete(
    "/projects/{project_id}/uploads/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_upload(project_id: str, upload_id: str, db: Session = Depends(get_db)):
    upload = (
        db.query(Upload)
        .filter(Upload.id == upload_id, Upload.project_id == project_id)
        .first()
    )
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    # Delete file from disk
    file_path = Path(settings.data_dir) / upload.file_path
    if file_path.exists():
        file_path.unlink()

    db.delete(upload)
    db.commit()
