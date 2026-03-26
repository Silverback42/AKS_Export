"""Parse Revit Excel export into standardized JSON format.

Refactored from tools/parse_revit_export.py — now importable as a function.
"""

from pathlib import Path

import openpyxl


COLUMN_PATTERNS = {
    "guid": ["ifcguid", "ifc_guid", "guid"],
    "room": ["raumnummer", "room number"],
    "type": ["familie und typ", "family and type"],
    "x": ["projectbasepoint_x", "basepoint_x"],
    "y": ["projectbasepoint_y", "basepoint_y"],
    "tables_id": ["tables id", "tablesid", "tables_id"],
}


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _match_column(header: str, patterns: list[str]) -> bool:
    header_lower = header.lower().strip()
    return any(p in header_lower for p in patterns)


def _detect_columns(headers: list[str | None]) -> dict[str, int]:
    mapping = {}
    for col_idx, header in enumerate(headers):
        if header is None:
            continue
        for logical_name, patterns in COLUMN_PATTERNS.items():
            if logical_name not in mapping and _match_column(str(header), patterns):
                mapping[logical_name] = col_idx
    return mapping


def parse_revit_export(
    excel_path: str | Path,
    equipment_type: str = "unknown",
    on_progress: callable = None,
) -> dict:
    """Parse Revit Excel export into structured format.

    Args:
        excel_path: Pfad zur Revit-Excel-Datei
        equipment_type: Equipment-Typ-Label (z.B. "Leuchte")
        on_progress: Callback(progress_pct, message)
    """
    if on_progress:
        on_progress(10, "Oeffne Excel...")

    wb = openpyxl.load_workbook(str(excel_path), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        wb.close()
        raise ValueError("Leere Excel-Datei")

    headers = [str(h) if h else None for h in rows[0]]
    col_map = _detect_columns(headers)

    required = ["guid", "room", "x", "y"]
    missing = [r for r in required if r not in col_map]
    if missing:
        wb.close()
        raise ValueError(f"Fehlende Spalten: {missing}. Gefundene Header: {headers}")

    if on_progress:
        on_progress(30, f"Parse {len(rows) - 1} Zeilen...")

    elements = []
    for row in rows[1:]:
        if all(cell is None for cell in row):
            continue

        element = {
            "guid": row[col_map["guid"]],
            "room": str(row[col_map["room"]]).strip() if row[col_map["room"]] else None,
            "revit_x": _safe_float(row[col_map["x"]]),
            "revit_y": _safe_float(row[col_map["y"]]),
        }

        if "type" in col_map and row[col_map["type"]]:
            element["type_description"] = str(row[col_map["type"]])
        if "tables_id" in col_map and row[col_map["tables_id"]]:
            element["tables_id"] = str(row[col_map["tables_id"]])

        elements.append(element)

    wb.close()

    if on_progress:
        on_progress(70, "Berechne Raum-Statistiken...")

    # Raum-Statistiken
    room_stats = {}
    for el in elements:
        room = el["room"]
        if room not in room_stats:
            room_stats[room] = {"count": 0, "xs": [], "ys": []}
        room_stats[room]["count"] += 1
        if el["revit_x"] is not None:
            room_stats[room]["xs"].append(el["revit_x"])
        if el["revit_y"] is not None:
            room_stats[room]["ys"].append(el["revit_y"])

    clean_stats = {}
    for room, stats in room_stats.items():
        xs, ys = stats["xs"], stats["ys"]
        x_range = max(xs) - min(xs) if len(xs) > 1 else 0.0
        y_range = max(ys) - min(ys) if len(ys) > 1 else 0.0
        clean_stats[room] = {
            "count": stats["count"],
            "x_range": round(x_range, 3),
            "y_range": round(y_range, 3),
            "dominant_axis": "X" if x_range > y_range else "Y",
        }

    if on_progress:
        on_progress(90, f"{len(elements)} Elemente geparst")

    return {
        "metadata": {
            "source_file": str(excel_path),
            "equipment_type": equipment_type,
            "total_count": len(elements),
            "original_headers": headers,
            "column_mapping": {k: headers[v] for k, v in col_map.items()},
        },
        "elements": elements,
        "room_stats": clean_stats,
    }
