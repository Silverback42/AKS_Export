"""Extraction service — orchestrates Schema/Grundriss extraction and registry building.

Wraps the core tools with project-specific config and manages intermediate JSON files.
"""

import json
from pathlib import Path

from app.config import settings
from app.core.tools import extract_schema_aks, extract_grundriss_aks, build_registry, export_aks_registry_excel


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


def run_schema_extraction(
    on_progress,
    project_id: str,
    pdf_path: str,
    aks_regex: str,
    room_code_pattern: str,
    room_format: str,
) -> str:
    """Schema-AKS aus PDF extrahieren und als JSON speichern.

    Returns:
        Pfad zur Ergebnis-JSON (relativ zu data_dir)
    """
    result = extract_schema_aks(
        pdf_path=pdf_path,
        aks_regex=aks_regex,
        room_code_pattern=room_code_pattern,
        room_format=room_format,
        on_progress=on_progress,
    )

    out_dir = _intermediate_dir(project_id)
    out_path = out_dir / "schema_aks.json"
    _save_json(result, out_path)

    on_progress(100, f"{result['metadata']['total_aks_unique']} AKS extrahiert")
    return str(out_path)


def run_grundriss_extraction(
    on_progress,
    project_id: str,
    pdf_path: str,
    aks_regex: str,
    room_code_pattern: str,
    room_format: str,
    geraet_type_map: dict,
) -> str:
    """Grundriss-AKS aus PDF extrahieren und als JSON speichern."""
    result = extract_grundriss_aks(
        pdf_path=pdf_path,
        aks_regex=aks_regex,
        room_code_pattern=room_code_pattern,
        room_format=room_format,
        geraet_type_map=geraet_type_map,
        on_progress=on_progress,
    )

    out_dir = _intermediate_dir(project_id)
    out_path = out_dir / "grundriss_aks.json"
    _save_json(result, out_path)

    on_progress(100, f"{result['metadata']['total_aks']} AKS extrahiert")
    return str(out_path)


def run_registry_build(
    on_progress,
    project_id: str,
) -> str:
    """Schema + Grundriss zu AKS-Registry zusammenfuehren."""
    inter_dir = _intermediate_dir(project_id)
    schema_path = inter_dir / "schema_aks.json"
    grundriss_path = inter_dir / "grundriss_aks.json"

    if not schema_path.exists():
        raise FileNotFoundError("Schema-Extraktion fehlt. Bitte zuerst Schema-PDF extrahieren.")
    if not grundriss_path.exists():
        raise FileNotFoundError("Grundriss-Extraktion fehlt. Bitte zuerst Grundriss-PDF extrahieren.")

    on_progress(5, "Lade Extraktionsdaten...")
    schema_data = _load_json(schema_path)
    grundriss_data = _load_json(grundriss_path)

    result = build_registry(schema_data, grundriss_data, on_progress=on_progress)

    out_path = inter_dir / "aks_registry.json"
    _save_json(result, out_path)

    meta = result["metadata"]
    on_progress(100, f"{meta['total_equipment']} Equipment, {meta['with_schema']} mit Schema")
    return str(out_path)


def run_aks_excel_export(
    on_progress,
    project_id: str,
) -> str:
    """AKS-Registry als Excel exportieren."""
    inter_dir = _intermediate_dir(project_id)
    registry_path = inter_dir / "aks_registry.json"

    if not registry_path.exists():
        raise FileNotFoundError("AKS-Registry fehlt. Bitte zuerst Registry bauen.")

    on_progress(5, "Lade Registry...")
    registry_data = _load_json(registry_path)

    export_dir = Path(settings.data_dir) / "projects" / project_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / "aks_registry.xlsx"

    export_aks_registry_excel(registry_data, out_path, on_progress=on_progress)

    on_progress(100, "Excel erstellt")
    return str(out_path)
