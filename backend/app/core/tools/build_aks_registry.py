"""Build unified AKS registry from Schema and Grundriss extractions.

Refactored from tools/build_aks_registry.py — now importable as a function.
"""

from collections import defaultdict


def build_registry(
    schema_data: dict,
    grundriss_data: dict,
    on_progress: callable = None,
) -> dict:
    """Merge Schema and Grundriss AKS into unified registry.

    Args:
        schema_data: Ergebnis von extract_schema_aks()
        grundriss_data: Ergebnis von extract_grundriss_aks()
        on_progress: Callback(progress_pct, message)
    """
    if on_progress:
        on_progress(10, "Indexiere Schema-AKS...")

    # Schema-AKS nach Prefix indexieren
    schema_by_prefix = defaultdict(list)
    for entry in schema_data["aks_entries"]:
        aks = entry["aks_full"]
        parts = aks.split("_")
        for depth in range(6, len(parts)):
            prefix = "_".join(parts[:depth])
            schema_by_prefix[prefix.lower()].append(entry)

    if on_progress:
        on_progress(30, "Baue Equipment-Registry...")

    # Equipment aus Grundriss-AKS
    equipment = []
    for entry in grundriss_data["aks_entries"]:
        aks = entry["aks"]
        aks_lower = aks.lower()

        children = schema_by_prefix.get(aks_lower, [])
        child_aks = sorted(set(c["aks_full"] for c in children))
        child_pages = sorted(set(c["source_page"] for c in children))

        eq = {
            "aks_parent": aks,
            "room": entry.get("raum"),
            "raum_code": entry.get("raum_code"),
            "anlage": entry.get("anlage"),
            "gewerk": entry.get("gewerk"),
            "geraet": entry.get("geraet"),
            "geraet_type": entry.get("geraet_type"),
            "pdf_x": entry.get("pdf_x"),
            "pdf_y": entry.get("pdf_y"),
            "depth": entry.get("depth", len(aks.split("_"))),
            "schema_children": child_aks,
            "schema_pages": child_pages,
            "has_schema": len(child_aks) > 0,
            "source": "grundriss",
        }
        equipment.append(eq)

    if on_progress:
        on_progress(60, "Resolve Querverweise...")

    # Querverweise aufloesen
    cross_refs = []
    for ref in grundriss_data.get("cross_references", []):
        anlage = ref.get("anlage")
        resolved = {
            "text": ref.get("text"),
            "type": ref.get("type"),
            "anlage": anlage,
            "pdf_x": ref.get("pdf_x"),
            "pdf_y": ref.get("pdf_y"),
        }

        if anlage and anlage in schema_data.get("anlagen", {}):
            anlage_info = schema_data["anlagen"][anlage]
            resolved["schema_pages"] = anlage_info.get("pages", [])
            resolved["description"] = anlage_info.get("description")
            resolved["room_ref"] = anlage_info.get("room_ref")
            resolved["resolved"] = True
        else:
            resolved["resolved"] = anlage != "UNRESOLVED"

        cross_refs.append(resolved)

    if on_progress:
        on_progress(80, "Baue Indizes...")

    # Raum-Index
    room_index = defaultdict(list)
    for eq in equipment:
        if eq["room"]:
            room_index[eq["room"]].append(eq["aks_parent"])

    # Anlagen-Index
    anlage_index = {}
    for code, info in schema_data.get("anlagen", {}).items():
        anlage_index[code] = {
            "description": info.get("description"),
            "room_ref": info.get("room_ref"),
            "pages": info.get("pages", []),
            "aks_count": sum(1 for e in schema_data["aks_entries"] if e.get("anlage") == code),
        }

    with_schema = sum(1 for eq in equipment if eq["has_schema"])
    orphans = sum(1 for eq in equipment if not eq["has_schema"])

    if on_progress:
        on_progress(90, f"{len(equipment)} Equipment, {with_schema} mit Schema")

    return {
        "metadata": {
            "total_equipment": len(equipment),
            "with_schema": with_schema,
            "orphans": orphans,
            "total_schema_aks": len(schema_data["aks_entries"]),
            "total_cross_refs": len(cross_refs),
            "resolved_cross_refs": sum(1 for r in cross_refs if r.get("resolved")),
        },
        "equipment": equipment,
        "cross_references": cross_refs,
        "room_index": dict(room_index),
        "anlage_index": anlage_index,
    }
