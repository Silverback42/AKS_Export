"""Matching service — orchestrates Revit parsing, matching, and export.

Wraps the core tools with project-specific config and manages intermediate JSON files.
"""

import json
from pathlib import Path

from app.config import settings
from app.core.tools import parse_revit_export, match_revit_to_aks, export_revit_import_excel


def _intermediate_dir(project_id: str) -> Path:
    path = Path(settings.data_dir) / "projects" / project_id / "intermediate"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_json(data: dict, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_revit_parse(
    on_progress,
    project_id: str,
    excel_path: str,
    equipment_type: str,
) -> str:
    """Revit-Excel parsen und als JSON speichern."""
    result = parse_revit_export(
        excel_path=excel_path,
        equipment_type=equipment_type,
        on_progress=on_progress,
    )

    out_dir = _intermediate_dir(project_id)
    out_path = out_dir / "revit_elements.json"
    _save_json(result, out_path)

    on_progress(100, f"{result['metadata']['total_count']} Elemente geparst")
    return str(out_path)


def run_matching(
    on_progress,
    project_id: str,
    equipment_filter: str,
) -> str:
    """Revit-Elemente mit AKS-Registry matchen."""
    inter_dir = _intermediate_dir(project_id)
    registry_path = inter_dir / "aks_registry.json"
    revit_path = inter_dir / "revit_elements.json"

    if not registry_path.exists():
        raise FileNotFoundError("AKS-Registry fehlt. Bitte zuerst Registry bauen (Phase 2).")
    if not revit_path.exists():
        raise FileNotFoundError("Revit-Daten fehlen. Bitte zuerst Revit-Excel parsen.")

    on_progress(5, "Lade Daten...")
    registry_data = _load_json(registry_path)
    revit_data = _load_json(revit_path)

    result = match_revit_to_aks(
        registry_data, revit_data, equipment_filter, on_progress=on_progress
    )

    out_path = inter_dir / "match_results.json"
    _save_json(result, out_path)

    meta = result["metadata"]
    on_progress(100, f"{meta['total_matched']} Matches, {meta['total_unmatched_aks']} unmatched")
    return str(out_path)


def run_revit_import_export(
    on_progress,
    project_id: str,
    original_excel_path: str,
) -> str:
    """Revit-Import-Excel mit AKS-Zuordnungen exportieren."""
    inter_dir = _intermediate_dir(project_id)
    match_path = inter_dir / "match_results.json"

    if not match_path.exists():
        raise FileNotFoundError("Match-Ergebnisse fehlen. Bitte zuerst Matching ausfuehren.")

    on_progress(5, "Lade Match-Ergebnisse...")
    match_data = _load_json(match_path)

    export_dir = Path(settings.data_dir) / "projects" / project_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / "revit_import.xlsx"

    export_revit_import_excel(match_data, original_excel_path, out_path, on_progress=on_progress)

    on_progress(100, "Revit-Import Excel erstellt")
    return str(out_path)
