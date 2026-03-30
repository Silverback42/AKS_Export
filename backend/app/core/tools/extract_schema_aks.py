"""Extract all AKS identifiers from Schema PDF with metadata.

Refactored from tools/extract_schema_aks.py — AKS regex is now a parameter
instead of hardcoded WUN005.
"""

import re
from pathlib import Path

import fitz

from app.core.tools.aks_structure import EBENE_PREFIX


def _convert_room(raum_code: str, room_code_pattern: str, room_format: str) -> str:
    """Raum-Code in lesbares Format umwandeln (EG441 -> E.441, KG580 -> K.580)."""
    # Sonderfaelle
    if raum_code == "DA000":
        return "Dach"
    if raum_code.endswith("000"):
        return "Allgemein"

    # Erweiterte Erkennung: (EG|KG|OG|DA) + Ziffern
    ebene_match = re.match(r"(EG|KG|OG|DA)(\d{3})", raum_code)
    if ebene_match:
        prefix = EBENE_PREFIX.get(ebene_match.group(1), ebene_match.group(1))
        return f"{prefix}.{ebene_match.group(2)}"

    # Fallback: Projekt-spezifisches Pattern (Rueckwaertskompatibilitaet)
    room_match = re.match(room_code_pattern, raum_code)
    if room_match:
        return room_format.format(room_match.group(1))

    return raum_code


def parse_aks(aks_str: str, room_code_pattern: str, room_format: str) -> dict | None:
    """Parse AKS string into components using project-specific room patterns.

    Unterstuetzte Formate:
    - 6-teilig (Grundriss): PROJEKT_GEWERK_ANLAGE+NR_ASP_RAUM_GERAET
    - 7-teilig (Schema):    PROJEKT_GEWERK_ANLAGE+NR_ASP_RAUM_GERAET_FUNKTION
    - 8-teilig (MSR):       PROJEKT_GEWERK_ANLAGE+NR_ASP_RAUM_GERAET_FUNKTIONSCODE_NR
    """
    parts = aks_str.split("_")
    if len(parts) < 6:
        return None

    # Anlage aufteilen: RLT004 -> anlage=RLT, anlage_nr=004
    anlage_full = parts[2]
    anlage_letters = re.match(r"^([A-Za-zÖÜÄöüä]+)", anlage_full)
    if anlage_letters:
        anlage_name = anlage_letters.group(1)
        anlage_nr = anlage_full[len(anlage_name):]
    else:
        anlage_name = anlage_full
        anlage_nr = ""

    result = {
        "aks_full": aks_str,
        "projekt": parts[0],
        "gewerk": parts[1],
        "anlage": anlage_full,
        "anlage_prefix": anlage_name,
        "anlage_nr": anlage_nr,
        "anlage_full": anlage_full,
        "asp": parts[3],
        "raum_code": parts[4],
        "raum": _convert_room(parts[4], room_code_pattern, room_format),
        "geraet": parts[5],
        "depth": len(parts),
    }

    # 7-teilig: Funktion (z.B. RAU01, Anst03)
    if len(parts) >= 7:
        result["funktion"] = parts[6]

    # 8-teilig: MSR-Funktionscode (z.B. SW_01 -> funktion=SW, funktion_nr=01)
    if len(parts) >= 8:
        result["funktion"] = parts[6]
        result["funktion_nr"] = parts[7]
        result["funktionscode"] = f"{parts[6]}_{parts[7]}"

    # 9+ Teile: Rest zusammenfassen
    if len(parts) >= 9:
        result["sub_funktion"] = "_".join(parts[8:])

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

        anlage_match = re.match(r"^=([A-Za-z]{2,}\d{2,})", text)
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

        # Beschreibungs-Index aufbauen: AKS-Strings sind vertikal gedreht,
        # Beschreibung steht unterhalb des AKS-Strings mit aehnlichem x-Wert.
        # Ausschluss: kurze Texte (<= 3 Zeichen), rein numerische Texte, AKS-Strings.
        beschreibung_by_aks: dict[str, str] = {}
        all_page_items = []
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                t = "".join(span["text"] for span in line["spans"]).strip()
                if t:
                    bbox = line["bbox"]
                    all_page_items.append({
                        "text": t,
                        "x": bbox[0], "y": bbox[1],
                        "x2": bbox[2], "y2": bbox[3],
                    })

        for item in all_page_items:
            aks_m = compiled_regex.search(item["text"])
            if not aks_m:
                continue
            aks_found = aks_m.group(0)
            if aks_found in beschreibung_by_aks:
                continue
            # Kandidaten: unterhalb des AKS (y_top > aks_y2), aehnlicher x-Bereich (|x - aks_x| < 20pt)
            candidates = [
                n for n in all_page_items
                if n["y"] > item["y2"] - 5
                and abs(n["x"] - item["x"]) < 20
                and not compiled_regex.search(n["text"])
                and len(n["text"]) > 3
                and not re.match(r"^\d+$", n["text"])
            ]
            candidates.sort(key=lambda n: n["y"])
            if candidates:
                beschreibung_by_aks[aks_found] = candidates[0]["text"]

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
                # Interne AKS herausfiltern: Betriebsmittel darf nicht rein numerisch sein
                # (z.B. "01", "02" sind interne Planungssymbole, werden nicht gezeichnet)
                geraet = parsed.get("geraet", "")
                if geraet and re.match(r"^\d+$", geraet):
                    continue
                parsed["source_page"] = i + 1
                parsed["page_type"] = page_type
                parsed["anlage_ref"] = title["anlage_code"]
                parsed["beschreibung"] = beschreibung_by_aks.get(aks_str)
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
