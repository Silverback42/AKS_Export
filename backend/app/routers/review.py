"""Review API endpoints — Korrekturen fuer Match-Ergebnisse verwalten."""

import copy
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MatchCorrection, Project, Task
from app.schemas import (
    CorrectionCreate,
    CorrectionListResponse,
    CorrectionResponse,
    ReviewDataResponse,
)

router = APIRouter(tags=["review"])


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_match_task_or_404(project_id: str, task_id: str, db: Session) -> Task:
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.project_id == project_id, Task.task_type == "match_revit")
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Match-Task nicht gefunden")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail=f"Task nicht abgeschlossen (Status: {task.status})")
    return task


def _load_match_data(task: Task) -> dict:
    if not task.result_path:
        raise HTTPException(status_code=404, detail="Match-Ergebnisse nicht gefunden")
    match_path = Path(task.result_path)
    if not match_path.exists():
        raise HTTPException(status_code=404, detail="Match-Ergebnisse-Datei nicht gefunden")
    with open(match_path, encoding="utf-8") as f:
        return json.load(f)


def _apply_corrections_to_data(match_data: dict, corrections: list[MatchCorrection]) -> dict:
    """Korrekturen auf Match-Daten anwenden und neues Ergebnis zurueckgeben."""
    data = copy.deepcopy(match_data)

    for correction in corrections:
        if correction.correction_type == "swap":
            _apply_swap(data, correction)
        elif correction.correction_type == "unmatch":
            _apply_unmatch(data, correction)
        elif correction.correction_type == "manual_match":
            _apply_manual_match(data, correction)

    # Room-Summary neu berechnen
    _recalculate_room_summary(data)
    return data


def _apply_swap(data: dict, correction: MatchCorrection):
    """AKS zwischen zwei Matches tauschen."""
    match_a = None
    match_b = None

    for m in data["matches"]:
        if m["revit_guid"] == correction.revit_guid:
            match_a = m
        if m.get("aks") == correction.corrected_aks and m["room"] == correction.room:
            match_b = m

    if match_a and match_b:
        match_a["aks"], match_b["aks"] = match_b["aks"], match_a["aks"]
        match_a["confidence"] = "CORRECTED"
        match_b["confidence"] = "CORRECTED"


def _apply_unmatch(data: dict, correction: MatchCorrection):
    """Match aufloesen — AKS und Revit-Element in Unmatched verschieben."""
    match = None
    for i, m in enumerate(data["matches"]):
        if m["revit_guid"] == correction.revit_guid:
            match = data["matches"].pop(i)
            break

    if match:
        data["unmatched_aks"].append({
            "room": match["room"],
            "aks": match["aks"],
            "reason": "manually_unmatched",
        })
        data["unmatched_revit"].append({
            "room": match["room"],
            "guid": match["revit_guid"],
            "reason": "manually_unmatched",
        })


def _apply_manual_match(data: dict, correction: MatchCorrection):
    """Manuell ein AKS mit einem Revit-Element paaren."""
    # AKS aus unmatched entfernen
    aks_entry = None
    for i, um in enumerate(data["unmatched_aks"]):
        if um.get("aks") == correction.corrected_aks and um.get("room") == correction.room:
            aks_entry = data["unmatched_aks"].pop(i)
            break

    # Revit-Element aus unmatched entfernen
    revit_entry = None
    for i, um in enumerate(data["unmatched_revit"]):
        if um.get("guid") == correction.revit_guid:
            revit_entry = data["unmatched_revit"].pop(i)
            break

    if aks_entry and revit_entry:
        data["matches"].append({
            "room": correction.room,
            "aks": correction.corrected_aks,
            "revit_guid": correction.revit_guid,
            "revit_type": "",
            "revit_x": None,
            "revit_y": None,
            "pdf_x": None,
            "pdf_y": None,
            "sort_axis": "MANUAL",
            "sort_rank": 0,
            "confidence": "CORRECTED",
        })


def _recalculate_room_summary(data: dict):
    """Room-Summary basierend auf aktuellem Match-Zustand neu berechnen."""
    summary = {}

    # Matches zaehlen + Confidence-Flags pro Raum sammeln (O(n))
    room_flags: dict[str, dict[str, bool]] = {}
    for m in data["matches"]:
        room = m["room"]
        if room not in summary:
            summary[room] = {"matched": 0, "aks_count": 0, "revit_count": 0, "status": "MATCHED"}
            room_flags[room] = {"has_corrected": False, "has_medium": False}
        summary[room]["matched"] += 1
        summary[room]["aks_count"] += 1
        summary[room]["revit_count"] += 1

        flags = room_flags.setdefault(room, {"has_corrected": False, "has_medium": False})
        if m.get("confidence") == "CORRECTED":
            flags["has_corrected"] = True
        elif m.get("confidence") == "MEDIUM":
            flags["has_medium"] = True

    # Confidence pro Raum setzen
    for room, flags in room_flags.items():
        if flags["has_corrected"]:
            summary[room]["confidence"] = "CORRECTED"
        elif flags["has_medium"]:
            summary[room]["confidence"] = "MEDIUM"
        else:
            summary[room]["confidence"] = "HIGH"

    # Unmatched AKS zaehlen
    for um in data["unmatched_aks"]:
        room = um.get("room")
        if room and room not in summary:
            summary[room] = {"matched": 0, "aks_count": 0, "revit_count": 0, "status": "NO_REVIT"}
        if room:
            summary[room]["aks_count"] += 1

    # Unmatched Revit zaehlen
    for um in data["unmatched_revit"]:
        room = um.get("room")
        if room and room not in summary:
            summary[room] = {"matched": 0, "aks_count": 0, "revit_count": 0, "status": "NO_AKS"}
        if room:
            summary[room]["revit_count"] += 1

    # Status aktualisieren
    for s in summary.values():
        if s["matched"] > 0 and s["aks_count"] == s["revit_count"] == s["matched"]:
            s["status"] = "MATCHED"
        elif s["aks_count"] != s["revit_count"]:
            s["status"] = "COUNT_MISMATCH"

    data["room_summary"] = summary


@router.get("/projects/{project_id}/match/{task_id}/review", response_model=ReviewDataResponse)
def get_review_data(project_id: str, task_id: str, db: Session = Depends(get_db)):
    """Review-Daten laden: Match-Ergebnisse mit angewandten Korrekturen."""
    _get_project_or_404(project_id, db)
    task = _get_match_task_or_404(project_id, task_id, db)
    match_data = _load_match_data(task)

    corrections = (
        db.query(MatchCorrection)
        .filter(MatchCorrection.project_id == project_id, MatchCorrection.task_id == task_id)
        .order_by(MatchCorrection.created_at)
        .all()
    )

    corrected_data = _apply_corrections_to_data(match_data, corrections)

    return ReviewDataResponse(
        matches=corrected_data["matches"],
        unmatched_aks=corrected_data["unmatched_aks"],
        unmatched_revit=corrected_data["unmatched_revit"],
        room_summary=corrected_data["room_summary"],
        corrections=[CorrectionResponse.model_validate(c) for c in corrections],
    )


@router.post("/projects/{project_id}/match/{task_id}/corrections", response_model=CorrectionResponse, status_code=201)
def create_correction(
    project_id: str,
    task_id: str,
    req: CorrectionCreate,
    db: Session = Depends(get_db),
):
    """Neue Korrektur speichern."""
    _get_project_or_404(project_id, db)
    _get_match_task_or_404(project_id, task_id, db)

    correction = MatchCorrection(
        project_id=project_id,
        task_id=task_id,
        room=req.room,
        revit_guid=req.revit_guid,
        original_aks=req.original_aks,
        corrected_aks=req.corrected_aks,
        correction_type=req.correction_type,
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)

    return CorrectionResponse.model_validate(correction)


@router.get("/projects/{project_id}/match/{task_id}/corrections", response_model=CorrectionListResponse)
def list_corrections(project_id: str, task_id: str, db: Session = Depends(get_db)):
    """Gespeicherte Korrekturen laden."""
    _get_project_or_404(project_id, db)

    corrections = (
        db.query(MatchCorrection)
        .filter(MatchCorrection.project_id == project_id, MatchCorrection.task_id == task_id)
        .order_by(MatchCorrection.created_at)
        .all()
    )

    return CorrectionListResponse(
        corrections=[CorrectionResponse.model_validate(c) for c in corrections]
    )


@router.delete("/projects/{project_id}/match/{task_id}/corrections/{correction_id}", status_code=204)
def delete_correction(
    project_id: str,
    task_id: str,
    correction_id: str,
    db: Session = Depends(get_db),
):
    """Einzelne Korrektur entfernen."""
    correction = (
        db.query(MatchCorrection)
        .filter(
            MatchCorrection.id == correction_id,
            MatchCorrection.project_id == project_id,
            MatchCorrection.task_id == task_id,
        )
        .first()
    )
    if not correction:
        raise HTTPException(status_code=404, detail="Korrektur nicht gefunden")

    db.delete(correction)
    db.commit()


@router.post("/projects/{project_id}/match/{task_id}/apply-corrections", response_model=ReviewDataResponse)
def apply_corrections(project_id: str, task_id: str, db: Session = Depends(get_db)):
    """Alle Korrekturen auf Match-Ergebnis anwenden und als neues JSON speichern."""
    _get_project_or_404(project_id, db)
    task = _get_match_task_or_404(project_id, task_id, db)
    match_data = _load_match_data(task)

    corrections = (
        db.query(MatchCorrection)
        .filter(MatchCorrection.project_id == project_id, MatchCorrection.task_id == task_id)
        .order_by(MatchCorrection.created_at)
        .all()
    )

    corrected_data = _apply_corrections_to_data(match_data, corrections)

    # Korrigierte Daten neben Original speichern
    result_path = Path(task.result_path)
    corrected_path = result_path.parent / f"match_results_{task_id}_corrected.json"
    with open(corrected_path, "w", encoding="utf-8") as f:
        json.dump(corrected_data, f, ensure_ascii=False, indent=2)

    return ReviewDataResponse(
        matches=corrected_data["matches"],
        unmatched_aks=corrected_data["unmatched_aks"],
        unmatched_revit=corrected_data["unmatched_revit"],
        room_summary=corrected_data["room_summary"],
        corrections=[CorrectionResponse.model_validate(c) for c in corrections],
    )
