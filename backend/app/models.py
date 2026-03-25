import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid4())


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    project_code = Column(String(50), nullable=False, unique=True)
    aks_regex = Column(String(255), nullable=False)
    room_code_pattern = Column(String(100), nullable=False, default=r"EG(\d{3})")
    room_format = Column(String(50), nullable=False, default="E.{0}")
    geraet_type_map = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    uploads = relationship("Upload", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

    def get_geraet_type_map(self) -> dict:
        return json.loads(self.geraet_type_map) if self.geraet_type_map else {}

    def set_geraet_type_map(self, value: dict):
        self.geraet_type_map = json.dumps(value)


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    project = relationship("Project", back_populates="uploads")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    task_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String(500), nullable=True)
    result_path = Column(String(1000), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    project = relationship("Project", back_populates="tasks")


class MatchCorrection(Base):
    __tablename__ = "match_corrections"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    room = Column(String(20), nullable=False)
    revit_guid = Column(String(50), nullable=False)
    original_aks = Column(String(255), nullable=True)
    corrected_aks = Column(String(255), nullable=True)
    correction_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    project = relationship("Project")
    task = relationship("Task")
