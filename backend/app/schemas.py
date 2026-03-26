from datetime import datetime

from pydantic import BaseModel, Field


# --- Project Schemas ---

class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    project_code: str = Field(..., min_length=1, max_length=50)
    aks_regex: str = Field(..., min_length=1)
    room_code_pattern: str = Field(default=r"EG(\d{3})")
    room_format: str = Field(default="E.{0}")
    geraet_type_map: dict[str, str] = Field(default_factory=lambda: {
        "E": "Leuchte",
        "M": "Motor/Ventil",
        "S": "Sensor/Schalter",
        "B": "Sensor",
        "A": "Aktor",
        "U": "Zaehler",
        "PF": "Pruefeinrichtung",
        "F": "Sicherheit/Frost",
    })


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    project_code: str | None = Field(default=None, min_length=1, max_length=50)
    aks_regex: str | None = Field(default=None, min_length=1)
    room_code_pattern: str | None = None
    room_format: str | None = None
    geraet_type_map: dict[str, str] | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    project_code: str
    aks_regex: str
    room_code_pattern: str
    room_format: str
    geraet_type_map: dict[str, str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    id: str
    name: str
    project_code: str
    created_at: datetime
    updated_at: datetime
    upload_count: int = 0

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectListItem]


class ProjectDetailResponse(ProjectResponse):
    uploads: list["UploadResponse"] = []


# --- Upload Schemas ---

class UploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadListResponse(BaseModel):
    uploads: list[UploadResponse]


# --- Task Schemas ---

class TaskResponse(BaseModel):
    id: str
    project_id: str
    task_type: str
    status: str
    progress: int
    message: str | None
    result_path: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]


# --- Registry Schemas ---

class RegistrySummaryResponse(BaseModel):
    metadata: dict
    room_index: dict[str, list[str]]
    equipment_count: int
    schema_aks_count: int
    cross_ref_count: int


# --- Matching Schemas ---

class MatchRequest(BaseModel):
    equipment_filter: str = Field(..., min_length=1, description="Equipment-Typ-Filter (z.B. 'Leuchte')")


class RevitParseRequest(BaseModel):
    equipment_type: str = Field(default="unknown", description="Equipment-Typ-Label")


class MatchResultsResponse(BaseModel):
    metadata: dict
    matches: list[dict]
    unmatched_aks: list[dict]
    unmatched_revit: list[dict]
    room_summary: dict
