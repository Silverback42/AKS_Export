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


def run_unified_extraction(
    on_progress,
    project_id: str,
    aks_regex_base: str,
    room_code_pattern: str,
    room_format: str,
    geraet_type_map: dict,
) -> str:
    """Alle PDFs eines Projekts extrahieren und Registry bauen (1 Schritt).

    Erkennt automatisch Schema- und Grundriss-PDFs anhand file_type,
    extrahiert alle parallel und baut die Registry.
    """
    from app.database import SessionLocal
    from app.models import Upload

    db = SessionLocal()
    try:
        uploads = (
            db.query(Upload)
            .filter(Upload.project_id == project_id)
            .filter(Upload.file_type.in_(["schema_pdf", "grundriss_pdf"]))
            .all()
        )
    finally:
        db.close()

    if not uploads:
        raise ValueError("Keine PDFs hochgeladen.")

    schema_pdfs = [u for u in uploads if u.file_type == "schema_pdf"]
    grundriss_pdfs = [u for u in uploads if u.file_type == "grundriss_pdf"]

    on_progress(2, f"{len(schema_pdfs)} Schema-PDFs, {len(grundriss_pdfs)} Grundriss-PDFs gefunden")

    # Schema-Regex: erzwingt 5-7 Unterstriche (6-8 Teile)
    schema_regex = aks_regex_base + r"[xX]?_\w+(?:_\w+){4,6}"
    # Grundriss-Regex: flexibler (variable Tiefe)
    grundriss_regex = aks_regex_base + r"[xX]?_\w+(?:_\w+)*"

    # --- Schema-PDFs extrahieren ---
    merged_schema = {
        "metadata": {"total_pages": 0, "total_aks_unique": 0, "total_aks_raw": 0},
        "anlagen": {},
        "pages": [],
        "aks_entries": [],
    }

    for i, upload in enumerate(schema_pdfs):
        pdf_path = Path(settings.data_dir) / upload.file_path
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"Upload-Datei fehlt auf Disk: {upload.filename} "
                f"(upload_id={upload.id}, path={upload.file_path})"
            )

        pct_base = 5 + int((i / max(len(schema_pdfs), 1)) * 40)
        on_progress(pct_base, f"Schema {i + 1}/{len(schema_pdfs)}: {upload.filename}")

        result = extract_schema_aks(
            pdf_path=str(pdf_path),
            aks_regex=schema_regex,
            room_code_pattern=room_code_pattern,
            room_format=room_format,
        )

        # Ergebnisse mergen
        merged_schema["metadata"]["total_pages"] += result["metadata"]["total_pages"]
        merged_schema["metadata"]["total_aks_raw"] += result["metadata"]["total_aks_raw"]
        merged_schema["aks_entries"].extend(result["aks_entries"])
        merged_schema["pages"].extend(result["pages"])
        for key, val in result["anlagen"].items():
            if key not in merged_schema["anlagen"]:
                merged_schema["anlagen"][key] = val
            else:
                merged_schema["anlagen"][key]["pages"].extend(val.get("pages", []))

    # Schema-AKS deduplizieren (Provenance mergen)
    seen = {}
    unique_aks = []
    for entry in merged_schema["aks_entries"]:
        key = entry["aks_full"]
        if key not in seen:
            seen[key] = entry
            unique_aks.append(entry)
        else:
            kept = seen[key]
            if "additional_pages" not in kept:
                kept["additional_pages"] = []
            if entry.get("source_page") and entry["source_page"] not in kept["additional_pages"]:
                kept["additional_pages"].append(entry["source_page"])
            if entry.get("source_file") and entry["source_file"] != kept.get("source_file"):
                if "additional_sources" not in kept:
                    kept["additional_sources"] = []
                if entry["source_file"] not in kept["additional_sources"]:
                    kept["additional_sources"].append(entry["source_file"])
    merged_schema["aks_entries"] = unique_aks
    merged_schema["metadata"]["total_aks_unique"] = len(unique_aks)

    on_progress(45, f"{len(unique_aks)} Schema-AKS extrahiert")

    # --- Grundriss-PDFs extrahieren ---
    merged_grundriss = {
        "metadata": {"total_aks": 0, "total_cross_refs": 0, "total_room_labels": 0},
        "aks_entries": [],
        "cross_references": [],
        "room_labels": [],
    }

    for i, upload in enumerate(grundriss_pdfs):
        pdf_path = Path(settings.data_dir) / upload.file_path
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"Upload-Datei fehlt auf Disk: {upload.filename} "
                f"(upload_id={upload.id}, path={upload.file_path})"
            )

        pct_base = 45 + int((i / max(len(grundriss_pdfs), 1)) * 30)
        on_progress(pct_base, f"Grundriss {i + 1}/{len(grundriss_pdfs)}: {upload.filename}")

        result = extract_grundriss_aks(
            pdf_path=str(pdf_path),
            aks_regex=grundriss_regex,
            room_code_pattern=room_code_pattern,
            room_format=room_format,
            geraet_type_map=geraet_type_map,
        )

        merged_grundriss["aks_entries"].extend(result["aks_entries"])
        merged_grundriss["cross_references"].extend(result["cross_references"])
        merged_grundriss["room_labels"].extend(result["room_labels"])

    merged_grundriss["metadata"]["total_aks"] = len(merged_grundriss["aks_entries"])
    merged_grundriss["metadata"]["total_cross_refs"] = len(merged_grundriss["cross_references"])
    merged_grundriss["metadata"]["total_room_labels"] = len(merged_grundriss["room_labels"])

    on_progress(75, f"{merged_grundriss['metadata']['total_aks']} Grundriss-AKS extrahiert")

    # --- Registry bauen ---
    on_progress(78, "Baue AKS-Registry...")
    registry = build_registry(merged_schema, merged_grundriss)

    # --- Ergebnisse speichern ---
    inter_dir = _intermediate_dir(project_id)
    _save_json(merged_schema, inter_dir / "schema_aks.json")
    _save_json(merged_grundriss, inter_dir / "grundriss_aks.json")

    registry_path = inter_dir / "aks_registry.json"
    _save_json(registry, registry_path)

    meta = registry["metadata"]
    on_progress(100, f"{meta['total_equipment']} Equipment, {meta['with_schema']} mit Schema")
    return str(registry_path)


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
