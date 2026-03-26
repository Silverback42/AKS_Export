"""Match Revit elements to AKS using Room + Position Sorting.

Refactored from tools/match_revit_to_aks.py — now importable as a function.
"""

from collections import defaultdict


def _filter_equipment(equipment: list[dict], equipment_filter: str) -> list[dict]:
    return [
        eq for eq in equipment
        if eq.get("geraet_type", "").lower() == equipment_filter.lower()
    ]


def _determine_sort_axis(revit_elements: list[dict]) -> tuple[str, str]:
    if len(revit_elements) <= 1:
        return "X", "SINGLE"

    xs = [e["revit_x"] for e in revit_elements if e.get("revit_x") is not None]
    ys = [e["revit_y"] for e in revit_elements if e.get("revit_y") is not None]

    x_range = max(xs) - min(xs) if len(xs) > 1 else 0
    y_range = max(ys) - min(ys) if len(ys) > 1 else 0

    return ("X", "RANGE") if x_range > y_range else ("Y", "RANGE")


def _sort_and_match(aks_entries: list[dict], revit_elements: list[dict], sort_axis: str) -> list[dict]:
    if sort_axis == "X":
        sorted_aks = sorted(aks_entries, key=lambda e: e.get("pdf_x", 0))
        sorted_revit = sorted(revit_elements, key=lambda e: e.get("revit_x", 0))
    else:
        sorted_aks = sorted(aks_entries, key=lambda e: e.get("pdf_y", 0))
        sorted_revit = sorted(revit_elements, key=lambda e: e.get("revit_y", 0), reverse=True)

    matches = []
    for rank, (aks, revit) in enumerate(zip(sorted_aks, sorted_revit)):
        matches.append({
            "room": aks.get("room") or revit.get("room"),
            "aks": aks["aks_parent"],
            "revit_guid": revit["guid"],
            "revit_type": revit.get("type_description", ""),
            "revit_x": revit.get("revit_x"),
            "revit_y": revit.get("revit_y"),
            "pdf_x": aks.get("pdf_x"),
            "pdf_y": aks.get("pdf_y"),
            "sort_axis": sort_axis,
            "sort_rank": rank + 1,
            "tables_id": revit.get("tables_id"),
        })

    return matches


def _compute_confidence(matches: list[dict], sort_axis: str):
    if len(matches) <= 1:
        for m in matches:
            m["confidence"] = "HIGH"
        return

    for m in matches:
        m["confidence"] = "HIGH"

    if sort_axis == "X":
        ys = [m["revit_y"] for m in matches if m["revit_y"] is not None]
        if ys and (max(ys) - min(ys)) > 2.0:
            for m in matches:
                m["confidence"] = "MEDIUM"
    else:
        xs = [m["revit_x"] for m in matches if m["revit_x"] is not None]
        if xs and (max(xs) - min(xs)) > 2.0:
            for m in matches:
                m["confidence"] = "MEDIUM"


def match_revit_to_aks(
    registry_data: dict,
    revit_data: dict,
    equipment_filter: str,
    on_progress: callable = None,
) -> dict:
    """Match Revit-Elemente zu AKS per Raum + Position.

    Args:
        registry_data: AKS-Registry (von build_registry)
        revit_data: Geparste Revit-Daten (von parse_revit_export)
        equipment_filter: Equipment-Typ-Filter (z.B. "Leuchte")
        on_progress: Callback(progress_pct, message)
    """
    equipment = _filter_equipment(registry_data["equipment"], equipment_filter)

    if not equipment:
        raise ValueError(f"Kein Equipment vom Typ '{equipment_filter}' in der Registry gefunden")

    if on_progress:
        on_progress(10, f"{len(equipment)} AKS vom Typ '{equipment_filter}' gefunden")

    # Nach Raum gruppieren
    aks_by_room = defaultdict(list)
    for eq in equipment:
        if eq.get("room"):
            aks_by_room[eq["room"]].append(eq)

    revit_by_room = defaultdict(list)
    for el in revit_data["elements"]:
        if el.get("room"):
            revit_by_room[el["room"]].append(el)

    all_matches = []
    unmatched_aks = []
    unmatched_revit = []
    room_summary = {}

    all_rooms = sorted(set(list(aks_by_room.keys()) + list(revit_by_room.keys())))
    total_rooms = len(all_rooms)

    for idx, room in enumerate(all_rooms):
        if on_progress:
            pct = 20 + int((idx / max(total_rooms, 1)) * 60)
            on_progress(pct, f"Raum {room} ({idx + 1}/{total_rooms})")

        aks_list = aks_by_room.get(room, [])
        revit_list = revit_by_room.get(room, [])

        if not aks_list and revit_list:
            for el in revit_list:
                unmatched_revit.append({"room": room, "guid": el["guid"], "reason": "no_aks_in_room"})
            room_summary[room] = {"matched": 0, "aks_count": 0, "revit_count": len(revit_list), "status": "NO_AKS"}
            continue

        if aks_list and not revit_list:
            for eq in aks_list:
                unmatched_aks.append({"room": room, "aks": eq["aks_parent"], "reason": "no_revit_in_room"})
            room_summary[room] = {"matched": 0, "aks_count": len(aks_list), "revit_count": 0, "status": "NO_REVIT"}
            continue

        if len(aks_list) != len(revit_list):
            room_summary[room] = {
                "matched": 0,
                "aks_count": len(aks_list),
                "revit_count": len(revit_list),
                "status": "COUNT_MISMATCH",
            }
            for eq in aks_list:
                unmatched_aks.append({"room": room, "aks": eq["aks_parent"], "reason": "count_mismatch"})
            for el in revit_list:
                unmatched_revit.append({"room": room, "guid": el["guid"], "reason": "count_mismatch"})
            continue

        # Counts stimmen ueberein — sortieren und matchen
        sort_axis, _ = _determine_sort_axis(revit_list)
        matches = _sort_and_match(aks_list, revit_list, sort_axis)
        _compute_confidence(matches, sort_axis)

        all_matches.extend(matches)
        room_summary[room] = {
            "matched": len(matches),
            "aks_count": len(aks_list),
            "revit_count": len(revit_list),
            "method": f"{sort_axis}-sort",
            "confidence": matches[0]["confidence"] if matches else "N/A",
            "status": "MATCHED",
        }

    if on_progress:
        on_progress(90, f"{len(all_matches)} Matches, {len(unmatched_aks)} unmatched")

    return {
        "metadata": {
            "equipment_filter": equipment_filter,
            "total_matched": len(all_matches),
            "total_unmatched_aks": len(unmatched_aks),
            "total_unmatched_revit": len(unmatched_revit),
            "rooms_processed": len(all_rooms),
        },
        "matches": all_matches,
        "unmatched_aks": unmatched_aks,
        "unmatched_revit": unmatched_revit,
        "room_summary": room_summary,
    }
