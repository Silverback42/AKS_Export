"""Extract all AKS identifiers from Schema PDF with metadata.

Refactored from tools/extract_schema_aks.py — AKS regex is now a parameter
instead of hardcoded WUN005.
"""

import re
from pathlib import Path

import fitz


def parse_aks(aks_str: str, room_code_pattern: str, room_format: str) -> dict | None:
    """Parse AKS string into components using project-specific room patterns."""
    parts = aks_str.split("_")
    if len(parts) < 6:
        return None

    result = {
        "aks_full": aks_str,
        "projekt": parts[0],
        "gewerk": parts[1],
        "anlage": parts[2],
        "asp": parts[3],
        "raum_code": parts[4],
    }

    # Raum-Code in lesbares Format umwandeln
    room_match = re.match(room_code_pattern, parts[4])
    if room_match:
        result["raum"] = room_format.format(room_match.group(1))
    elif parts[4] == "DA000":
        result["raum"] = "Dach"
    elif parts[4].endswith("000"):
        result["raum"] = "Allgemein"
    else:
        result["raum"] = parts[4]

    if len(parts) >= 6:
        result["geraet"] = parts[5]
    if len(parts) >= 7:
        result["funktion"] = parts[6]
    if len(parts) >= 8:
        result["sub_funktion"] = "_".join(parts[7:])

    result["depth"] = len(parts)
    return result


def classify_page(text: str) -> str:
    """Classify page type based on content."""
    text_lower = text.lower()
    if "regelschema" in text_lower and "regelstruktur" in text_lower:
        return "Regelschema"
    if "funktionsliste" in text_lower or "informationsliste" in text_lower:
        return "Funktionsliste"
    if "zustandsgraph" in text_lower:
        return "Zustandsgraph"
    if "parameterblatt" in text_lower or ("parameter" in text_lower and "wert" in text_lower):
        return "Parameterblatt"
    return "Sonstige"


def extract_title_block(page) -> dict:
    """Extract metadata from page title block (bottom area)."""
    blocks = page.get_text("dict")["blocks"]
    metadata = {
        "anlage_code": None,
        "anlage_description": None,
        "room_ref": None,
        "isp": None,
        "blatt": None,
        "blatt_von": None,
    }

    all_lines = []
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            bbox = line["bbox"]
            if text:
                all_lines.append({"text": text, "x": bbox[0], "y": bbox[1]})

    for entry in all_lines:
        text = entry["text"]

        anlage_match = re.match(r"^=(\w{3,}\d{3,})", text)
        if anlage_match:
            metadata["anlage_code"] = anlage_match.group(1)

        room_match = re.match(r"^E\.\d{3}$", text)
        if room_match:
            metadata["room_ref"] = text

        if "Informationsschwerpunkt:" in text:
            metadata["isp"] = text.replace("Informationsschwerpunkt:", "").strip()

        blatt_match = re.match(r"^(\d+)$", text)
        if blatt_match and entry["y"] > 1050:
            num = int(blatt_match.group(1))
            if metadata["blatt"] is None:
                metadata["blatt"] = num
            elif metadata["blatt_von"] is None:
                metadata["blatt_von"] = num

    for entry in all_lines:
        text = entry["text"]
        if entry["y"] > 900 and len(text) > 3 and not text.startswith("=") and not re.match(r"^\d+$", text):
            if not any(kw in text for kw in [
                "Ingenieur", "Kaiserstr", "Goslar", "Airbus", "Taufkirchen",
                "Wunstorf", "Datum", "Index", "Bearbeiter", "Schema", "erstellt",
                "Blatt", "Automationsschema", "ASP", "Kuhbach", "Schramm",
                "Informationsschwerpunkt", "Anlage:", "Weitergabe",
                "Zuwiderhandlung", "Rechte", "Telefon", "Fax", "mail",
                "Messerschmitt", "Defence", "MRO", "Gewerk", "VDI",
                "Informationsliste", "Funktionsliste"
            ]):
                if metadata["anlage_description"] is None:
                    metadata["anlage_description"] = text

    return metadata


def extract_schema_aks(
    pdf_path: str | Path,
    aks_regex: str,
    room_code_pattern: str = r"EG(\d{3})",
    room_format: str = "E.{0}",
    on_progress: callable = None,
) -> dict:
    """Extract all AKS from schema PDF.

    Args:
        pdf_path: Pfad zur Schema-PDF
        aks_regex: Regex-Pattern fuer AKS-Erkennung (z.B. "WUN005[xX]?_\\w+(?:_\\w+){4,6}")
        room_code_pattern: Regex fuer Raum-Code-Erkennung
        room_format: Format-String fuer Raum-Anzeige (z.B. "E.{0}")
        on_progress: Callback(progress_pct, message) fuer Fortschrittsmeldungen
    """
    doc = fitz.open(str(pdf_path))
    compiled_regex = re.compile(aks_regex)

    all_aks = []
    anlagen = {}
    page_info = []
    total_pages = len(doc)

    for i, page in enumerate(doc):
        if on_progress:
            pct = int((i / total_pages) * 80)
            on_progress(pct, f"Seite {i + 1}/{total_pages}")

        text = page.get_text()
        page_type = classify_page(text)
        title = extract_title_block(page)

        matches = compiled_regex.findall(text)
        unique_matches = list(dict.fromkeys(matches))

        if title["anlage_code"] and title["anlage_code"] not in anlagen:
            anlagen[title["anlage_code"]] = {
                "description": title["anlage_description"],
                "room_ref": title["room_ref"],
                "pages": [],
            }
        if title["anlage_code"] and title["anlage_code"] in anlagen:
            if (i + 1) not in anlagen[title["anlage_code"]]["pages"]:
                anlagen[title["anlage_code"]]["pages"].append(i + 1)
            if title["anlage_description"] and not anlagen[title["anlage_code"]]["description"]:
                anlagen[title["anlage_code"]]["description"] = title["anlage_description"]

        page_info.append({
            "page": i + 1,
            "type": page_type,
            "anlage_code": title["anlage_code"],
            "room_ref": title["room_ref"],
            "aks_count": len(unique_matches),
        })

        for aks_str in unique_matches:
            parsed = parse_aks(aks_str, room_code_pattern, room_format)
            if parsed:
                parsed["source_page"] = i + 1
                parsed["page_type"] = page_type
                parsed["anlage_ref"] = title["anlage_code"]
                all_aks.append(parsed)

    doc.close()

    if on_progress:
        on_progress(85, "Dedupliziere AKS...")

    # Deduplizieren
    seen = {}
    unique_aks = []
    for entry in all_aks:
        key = entry["aks_full"]
        if key not in seen:
            seen[key] = entry
            unique_aks.append(entry)
        else:
            if "additional_pages" not in seen[key]:
                seen[key]["additional_pages"] = []
            seen[key]["additional_pages"].append(entry["source_page"])

    if on_progress:
        on_progress(90, f"{len(unique_aks)} AKS extrahiert")

    return {
        "metadata": {
            "source_file": str(pdf_path),
            "total_pages": len(page_info),
            "total_aks_unique": len(unique_aks),
            "total_aks_raw": len(all_aks),
        },
        "anlagen": anlagen,
        "pages": page_info,
        "aks_entries": unique_aks,
    }
