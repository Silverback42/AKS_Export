"""Extract AKS identifiers and cross-references from Grundrissplan PDF.

Refactored from tools/extract_grundriss_aks.py — AKS regex and
geraet_type_map are now parameters.
"""

import re
from pathlib import Path

import fitz

from app.core.tools.aks_structure import EBENE_PREFIX


def raum_from_code(code: str, room_code_pattern: str, room_format: str) -> str:
    """Convert room code to readable format using project config."""
    # Sonderfaelle
    if code == "DA000":
        return "Dach"
    if code.endswith("000"):
        return "Allgemein"

    # Erweiterte Erkennung: EG/KG/OG/DA + Ziffern
    ebene_match = re.match(r"(EG|KG|OG|DA)(\d{3})", code)
    if ebene_match:
        prefix = EBENE_PREFIX.get(ebene_match.group(1), ebene_match.group(1))
        return f"{prefix}.{ebene_match.group(2)}"

    # Fallback: Projekt-spezifisches Pattern
    m = re.match(room_code_pattern, code)
    if m:
        return room_format.format(m.group(1))

    return code


def classify_geraet(geraet_code: str, geraet_type_map: dict[str, str]) -> str:
    """Classify equipment type from device code using project config."""
    prefix = re.match(r"([A-Za-z]+)", geraet_code)
    if not prefix:
        return "Unbekannt"
    p = prefix.group(1).upper()
    # Laengsten Prefix zuerst pruefen
    for key in sorted(geraet_type_map.keys(), key=len, reverse=True):
        if p.startswith(key.upper()):
            return geraet_type_map[key]
    return "Unbekannt"


def extract_grundriss_aks(
    pdf_path: str | Path,
    aks_regex: str,
    room_code_pattern: str = r"EG(\d{3})",
    room_format: str = "E.{0}",
    geraet_type_map: dict[str, str] | None = None,
    on_progress: callable = None,
) -> dict:
    """Extract all AKS, room labels, and cross-references with positions.

    Args:
        pdf_path: Pfad zur Grundriss-PDF
        aks_regex: Regex-Pattern fuer AKS-Erkennung
        room_code_pattern: Regex fuer Raum-Code-Erkennung
        room_format: Format-String fuer Raum-Anzeige
        geraet_type_map: Mapping von Geraete-Prefix zu Typ-Label
        on_progress: Callback(progress_pct, message)
    """
    if geraet_type_map is None:
        from app.core.tools.aks_structure import DEFAULT_GERAET_TYPE_MAP
        geraet_type_map = DEFAULT_GERAET_TYPE_MAP

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    page_size = [page.rect.width, page.rect.height]

    if on_progress:
        on_progress(10, "Lese Text-Spans...")

    blocks = page.get_text("dict")["blocks"]
    all_spans = []
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            bbox = line["bbox"]
            all_spans.append({
                "text": text,
                "x": bbox[0], "y": bbox[1],
                "x2": bbox[2], "y2": bbox[3],
                "cx": (bbox[0] + bbox[2]) / 2,
                "cy": (bbox[1] + bbox[3]) / 2,
            })

    if on_progress:
        on_progress(30, f"{len(all_spans)} Spans gefunden, extrahiere AKS...")

    compiled_regex = re.compile(aks_regex)
    # Projekt-Code aus Regex extrahieren fuer Normalisierung
    project_code_match = re.match(r"^(\w+?)(?:\[|_)", aks_regex)
    project_code = project_code_match.group(1) if project_code_match else None

    aks_entries = []
    cross_references = []
    room_labels = []

    for span in all_spans:
        text = span["text"]

        aks_match = compiled_regex.search(text)
        if aks_match:
            aks_str = aks_match.group(0)
            # Normalisierung: z.B. WUN005X -> WUN005x
            if project_code:
                aks_str = re.sub(
                    rf"^{re.escape(project_code)}X",
                    f"{project_code}x",
                    aks_str,
                    flags=re.IGNORECASE,
                )

            parts = aks_str.split("_")
            entry = {
                "aks": aks_str,
                "pdf_x": round(span["cx"], 1),
                "pdf_y": round(span["cy"], 1),
                "bbox": [round(span["x"], 1), round(span["y"], 1),
                         round(span["x2"], 1), round(span["y2"], 1)],
            }

            if len(parts) >= 6:
                entry["gewerk"] = parts[1]
                entry["anlage"] = parts[2]
                entry["asp"] = parts[3]
                entry["raum_code"] = parts[4]
                entry["raum"] = raum_from_code(parts[4], room_code_pattern, room_format)
                entry["geraet"] = parts[5]
                entry["geraet_type"] = classify_geraet(parts[5], geraet_type_map)
                entry["depth"] = len(parts)
                if len(parts) == 7:
                    entry["funktion"] = parts[6]
                elif len(parts) == 8:
                    entry["funktion"] = parts[6]
                    entry["funktion_nr"] = parts[7]
                    entry["funktionscode"] = f"{parts[6]}_{parts[7]}"
                elif len(parts) > 8:
                    entry["funktion"] = parts[6]
                    entry["sub_funktion"] = "_".join(parts[7:])

            aks_entries.append(entry)
            continue

        if "Siehe Regelschema" in text:
            ref = {
                "text": text,
                "pdf_x": round(span["cx"], 1),
                "pdf_y": round(span["cy"], 1),
            }
            inline_match = re.search(r"Siehe Regelschema\s+(\w{3,}\d{3,})", text)
            if inline_match:
                ref["type"] = "inline"
                ref["anlage"] = inline_match.group(1)
            else:
                ref["type"] = "standalone"
                ref["anlage"] = None
            cross_references.append(ref)
            continue

        room_match = re.match(r"^([EKODA]{1,2}\.\d{3})(?:[-\s].*)?$", text)
        if room_match:
            room_labels.append({
                "label": text,
                "room": room_match.group(1),
                "pdf_x": round(span["cx"], 1),
                "pdf_y": round(span["cy"], 1),
            })

    if on_progress:
        on_progress(60, "Resolve Querverweise...")

    # Standalone-Querverweise aufloesen
    for ref in cross_references:
        if ref["anlage"] is not None:
            continue
        candidates = []
        for span in all_spans:
            dy = span["y"] - ref["pdf_y"]
            dx = abs(span["cx"] - ref["pdf_x"])
            if 0 < dy < 25 and dx < 50:
                candidates.append(span)
        candidates.sort(key=lambda s: s["y"])

        for cand in candidates:
            anlage_match = re.match(r"^(\w{3,}\d{3,})$", cand["text"])
            if anlage_match:
                ref["anlage"] = anlage_match.group(1)
                break
            aks_match2 = compiled_regex.search(cand["text"])
            if aks_match2:
                parts = aks_match2.group(0).split("_")
                if len(parts) >= 3:
                    ref["anlage"] = parts[2]
                    ref["resolved_from_aks"] = aks_match2.group(0)
                break

        if ref["anlage"] is None:
            ref["anlage"] = "UNRESOLVED"

    # "Anpassung AKS" Eintraege
    for span in all_spans:
        if "Anpassung AKS" in span["text"]:
            cross_references.append({
                "text": span["text"],
                "type": "anpassung",
                "anlage": None,
                "pdf_x": round(span["cx"], 1),
                "pdf_y": round(span["cy"], 1),
            })

    doc.close()

    if on_progress:
        on_progress(90, f"{len(aks_entries)} AKS extrahiert")

    return {
        "metadata": {
            "source_file": str(pdf_path),
            "page_size": page_size,
            "total_aks": len(aks_entries),
            "total_cross_refs": len(cross_references),
            "total_room_labels": len(room_labels),
        },
        "aks_entries": aks_entries,
        "cross_references": cross_references,
        "room_labels": room_labels,
    }
