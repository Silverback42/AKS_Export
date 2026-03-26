"""Build unified AKS registry from Schema and Grundriss extractions.

Refactored from tools/build_aks_registry.py — now importable as a function.
"""

from collections import defaultdict

from app.core.tools.aks_structure import DEFAULT_GERAET_TYPE_MAP
from app.core.tools.extract_grundriss_aks import classify_geraet


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

    # Schema-AKS nach Prefix indexieren (fuer Parent-Child Matching)
    schema_by_prefix = defaultdict(list)
    for entry in schema_data["aks_entries"]:
        aks = entry["aks_full"]
        parts = aks.split("_")
        for depth in range(6, len(parts)):
            prefix = "_".join(parts[:depth])
            schema_by_prefix[prefix.lower()].append(entry)

    # Schema-AKS nach Anlage indexieren (fuer Querverweis-Expansion)
    schema_by_anlage = defaultdict(list)
    for entry in schema_data["aks_entries"]:
        if entry.get("anlage"):
            schema_by_anlage[entry["anlage"]].append(entry)

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

        # Projekt aus AKS-String extrahieren (erster Teil)
        parts = aks.split("_")
        projekt = parts[0] if parts else None

        eq = {
            "aks_parent": aks,
            "projekt": projekt,
            "room": entry.get("raum"),
            "raum_code": entry.get("raum_code"),
            "anlage": entry.get("anlage"),
            "gewerk": entry.get("gewerk"),
            "asp": entry.get("asp"),
            "geraet": entry.get("geraet"),
            "geraet_type": entry.get("geraet_type"),
            "pdf_x": entry.get("pdf_x"),
            "pdf_y": entry.get("pdf_y"),
            "depth": entry.get("depth", len(parts)),
            "schema_children": child_aks,
            "schema_pages": child_pages,
            "has_schema": len(child_aks) > 0,
            "source": "grundriss",
        }
        equipment.append(eq)

    if on_progress:
        on_progress(50, "Resolve Querverweise...")

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
        on_progress(65, "Expandiere Querverweise zu Equipment...")

    # Querverweise in Equipment expandieren
    existing_aks = {eq["aks_parent"].lower() for eq in equipment}
    expanded_count = 0

    for ref in cross_refs:
        if not ref.get("resolved") or not ref.get("anlage"):
            continue

        for schema_entry in schema_by_anlage.get(ref["anlage"], []):
            aks_full = schema_entry["aks_full"]
            if aks_full.lower() in existing_aks:
                continue

            eq = {
                "aks_parent": aks_full,
                "projekt": schema_entry.get("projekt"),
                "room": schema_entry.get("raum"),
                "raum_code": schema_entry.get("raum_code"),
                "anlage": schema_entry.get("anlage"),
                "gewerk": schema_entry.get("gewerk"),
                "asp": schema_entry.get("asp"),
                "geraet": schema_entry.get("geraet"),
                "geraet_type": classify_geraet(
                    schema_entry.get("geraet", ""), DEFAULT_GERAET_TYPE_MAP
                ),
                "pdf_x": ref.get("pdf_x"),
                "pdf_y": ref.get("pdf_y"),
                "depth": schema_entry.get("depth", len(aks_full.split("_"))),
                "schema_children": [],
                "schema_pages": (
                    [schema_entry["source_page"]]
                    if schema_entry.get("source_page")
                    else []
                ),
                "has_schema": True,
                "source": "cross_ref",
                "cross_ref_text": ref.get("text"),
                "cross_ref_anlage": ref.get("anlage"),
            }
            equipment.append(eq)
            existing_aks.add(aks_full.lower())
            expanded_count += 1

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
        on_progress(90, f"{len(equipment)} Equipment, {expanded_count} aus Querverweisen")

    return {
        "metadata": {
            "total_equipment": len(equipment),
            "with_schema": with_schema,
            "orphans": orphans,
            "total_schema_aks": len(schema_data["aks_entries"]),
            "total_cross_refs": len(cross_refs),
            "resolved_cross_refs": sum(1 for r in cross_refs if r.get("resolved")),
            "expanded_from_cross_refs": expanded_count,
        },
        "equipment": equipment,
        "cross_references": cross_refs,
        "room_index": dict(room_index),
        "anlage_index": anlage_index,
    }
