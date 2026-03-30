"""Extract AKS identifiers and cross-references from Grundrissplan PDF.

Refactored from tools/extract_grundriss_aks.py — AKS regex and
geraet_type_map are now parameters.
"""

import logging
import re
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)

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
    if not geraet_type_map:
        from app.core.tools.aks_structure import DEFAULT_GERAET_TYPE_MAP
        geraet_type_map = DEFAULT_GERAET_TYPE_MAP

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    page_size = [page.rect.width, page.rect.height]

    if on_progress:
        on_progress(10, "Lese Text-Spans und Symbole...")

    compiled_regex = re.compile(aks_regex)
    # Projekt-Code aus Regex extrahieren fuer Normalisierung
    project_code_match = re.match(r"^(\w+?)(?:\[|_)", aks_regex)
    project_code = project_code_match.group(1) if project_code_match else None

    blocks = page.get_text("dict")["blocks"]
    all_spans = []
    for block in blocks:
        if "lines" not in block:
            continue
        # Alle Zeilen des Blocks als Texte sammeln (fuer Beschreibungs-Extraktion)
        block_lines: list[str] = []
        for line in block["lines"]:
            t = "".join(span["text"] for span in line["spans"]).strip()
            if t:
                block_lines.append(t)

        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            bbox = line["bbox"]
            # Beschreibung = andere Zeilen im selben Block, ohne AKS-Strings und ohne Duplikate
            seen_desc: set[str] = set()
            desc_lines = []
            for other_line in block_lines:
                if other_line == text:
                    continue
                if compiled_regex.search(other_line):
                    continue  # AKS-Zeilen nicht als Beschreibung uebernehmen
                if other_line not in seen_desc:
                    seen_desc.add(other_line)
                    desc_lines.append(other_line)
            block_description = " ".join(desc_lines) if desc_lines else None
            all_spans.append({
                "text": text,
                "x": bbox[0], "y": bbox[1],
                "x2": bbox[2], "y2": bbox[3],
                "cx": (bbox[0] + bbox[2]) / 2,
                "cy": (bbox[1] + bbox[3]) / 2,
                "block_description": block_description,
            })

    # Bauteil-Position ermitteln — 4-stufige Methode:
    # 1. Vertikale Verbindungslinie (AKS-Label horizontal, Linie geht nach oben/unten)
    # 2. Horizontale Verbindungslinie (AKS-Label vertikal, Linie geht nach links/rechts)
    # 3. Gefuelltes Vektor-Symbol in der Naehe der Textbox
    # 4. Farb-basiertes Symbol (Leuchte=pink, Lueftung=gelb, Jalousie=teal, Elektro=schwarz)

    # Bekannte Bauteil-Farben (RGB, Toleranz 0.1):
    # Leuchten: pink/magenta (1, 0, 1) oder aehnlich
    # Lueftung: gelb (1, 1, 0)
    # Jalousie: teal (0, 0.5, 0.5) ca.
    # Elektro: schwarz (0, 0, 0)
    BAUTEIL_FARBEN = [
        (1.0, 0.0, 1.0),    # Leuchte — magenta/pink
        (1.0, 0.0, 0.5),    # Leuchte — variante
        (1.0, 1.0, 0.0),    # Lueftung — gelb
        (0.0, 0.5, 0.5),    # Jalousie — teal
        (0.0, 0.6, 0.6),    # Jalousie — variante
        (0.0, 0.0, 0.0),    # Elektro — schwarz
    ]

    def _color_is_bauteil(color) -> bool:
        if not color:
            return False
        for fc in BAUTEIL_FARBEN:
            if all(abs(color[i] - fc[i]) < 0.15 for i in range(3)):
                return True
        return False

    # Verbindungslinien sammeln: aus den Pfad-Segmenten (items) statt der Bounding-Box.
    # Jede Drawing kann mehrere "l"-Segmente enthalten (z.B. bei geknickten Fuehrungslinien).
    # vert_lines: (x_mid, y_top, y_bot, p0_y, p1_y) — senkrechte Segmente
    # horiz_lines: (x_left, x_right, y_mid)         — waagrechte Segmente
    # line_paths: Alle schwarzen Pfad-Drawings mit ihren Endpunkten fuer Knick-Erkennung
    #             [(pt_x, pt_y), ...] — alle Punkte des Pfades
    vert_lines = []
    horiz_lines = []
    line_paths = []   # [(x, y), ...]  — alle Eckpunkte jeder schwarzen Fuehrungslinie
    # Gefuellte Symbole (Groesse 3-80pt)
    symbol_centers = []   # (cx, cy)
    # Farb-Symbole als Fallback
    color_symbols = []    # (cx, cy)

    for drawing in page.get_drawings():
        try:
            r = drawing["rect"]
            w = r.x1 - r.x0
            h = r.y1 - r.y0
            color = drawing.get("color")
            fill = drawing.get("fill")
            is_black = color == (0.0, 0.0, 0.0) and fill is None

            # Fuehrungslinien: schwarz, ungefuellt, Bounding-Box-Diagonale > 30pt
            # Einzelne Segmente aus items[] auswerten statt nur die Gesamt-Bbox.
            if is_black:
                diag = (w ** 2 + h ** 2) ** 0.5
                if diag > 30:
                    # Alle Endpunkte dieser Drawing sammeln (fuer Knick-Pfade)
                    path_pts: list[tuple[float, float]] = []
                    for seg in drawing.get("items", []):
                        if seg[0] == "l":
                            p0, p1 = seg[1], seg[2]
                            path_pts.append((p0.x, p0.y))
                            path_pts.append((p1.x, p1.y))

                            dx_seg = abs(p1.x - p0.x)
                            dy_seg = abs(p1.y - p0.y)

                            # Senkrechtes Segment: Δx < 3pt, Δy > 30pt
                            if dx_seg < 3 and dy_seg > 30:
                                x_mid = (p0.x + p1.x) / 2
                                vert_lines.append((
                                    x_mid,
                                    min(p0.y, p1.y),   # y_top
                                    max(p0.y, p1.y),   # y_bot
                                    p0.y,              # Rohpunkt A
                                    p1.y,              # Rohpunkt B
                                ))

                            # Waagrechtes Segment: Δy < 3pt, Δx > 30pt
                            elif dy_seg < 3 and dx_seg > 30:
                                y_mid = (p0.y + p1.y) / 2
                                horiz_lines.append((
                                    min(p0.x, p1.x),
                                    max(p0.x, p1.x),
                                    y_mid,
                                ))

                    if path_pts:
                        # Duplikate entfernen und als Pfad speichern
                        unique_pts = list(dict.fromkeys(path_pts))
                        line_paths.append(unique_pts)

            # Gefuelltes Vektor-Symbol (nicht schwarz, sinnvolle Groesse)
            elif fill is not None and 3 < w < 80 and 3 < h < 80:
                cx_s = (r.x0 + r.x1) / 2
                cy_s = (r.y0 + r.y1) / 2
                symbol_centers.append((cx_s, cy_s))
                # Zusaetzlich als Farb-Symbol merken wenn Bauteil-Farbe
                if _color_is_bauteil(fill):
                    color_symbols.append((cx_s, cy_s))

            # Farb-Kontur ohne Fill (stroke only, Bauteil-Farbe)
            elif fill is None and 3 < w < 80 and 3 < h < 80 and _color_is_bauteil(color):
                color_symbols.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))

        except Exception as e:
            logger.warning("Fehler beim Lesen der Zeichnungsdaten aus PDF: %s", e, exc_info=True)
            continue

    def _find_equipment_pos(cx: float, cy: float) -> tuple[tuple | None, str]:
        """Ermittelt Equipment-Position fuer eine AKS-Textbox.

        Strategie (5 Methoden in Reihenfolge):
        1. Linie-V: Senkrechtes Segment nahe Label-x — den vom Label entfernten Endpunkt nehmen
        2. Linie-H: Waagrechtes Segment nahe Label-y — das vom Label weg zeigende Ende
        3. Linie-Pfad: Bei geknickten Fuehrungslinien — Endpunkt des gesamten Pfades der
           am weitesten vom Label entfernt liegt (nicht der Knick-Punkt)
        4. Symbol-an-Linie: Symbol (Farbe/gefuellt) in 30pt Radius um den Leitungsendpunkt
        5. Symbol-gefuellt / Symbol-Farbe: naechstes Symbol ohne Leitungshinweis
        6. Fallback-Text: Label-Mittelpunkt

        Returns:
            (pos, method) — pos ist (x, y) oder None
        """
        TOLERANZ_LINIE = 12.0  # pt — maximaler Abstand Label-Mitte zu Linie

        # --- Methode 1: Senkrechtes Segment ---
        # Endpunkt waehlen der am weitesten vom Label-y entfernt liegt (= Anlage)
        best_dx = TOLERANZ_LINIE
        best_line: tuple | None = None
        for lx, ly_top, ly_bot, p0y, p1y in vert_lines:
            dx = abs(lx - cx)
            # Segment muss Label ueberspannen oder eindeutig ober-/unterhalb liegen
            spans = ly_top < cy - 10 or ly_bot > cy + 10 or (ly_top <= cy <= ly_bot)
            if dx < best_dx and spans:
                best_dx = dx
                # Den Endpunkt nehmen der weiter vom Label-Mittelpunkt (cy) entfernt ist
                far_y = p0y if abs(p0y - cy) >= abs(p1y - cy) else p1y
                best_line = (lx, far_y)

        # --- Methode 2: Waagrechtes Segment ---
        best_dy = TOLERANZ_LINIE
        best_hline: tuple | None = None
        for lx_l, lx_r, ly in horiz_lines:
            dy = abs(ly - cy)
            if dy < best_dy:
                # Linie links vom Label: Endpunkt = linkes Ende (zeigt zur Anlage)
                if lx_r < cx - 10:
                    best_dy = dy
                    best_hline = (lx_l, ly)
                # Linie rechts vom Label: Endpunkt = rechtes Ende
                elif lx_l > cx + 10:
                    best_dy = dy
                    best_hline = (lx_r, ly)

        # Den besten Leitungs-Endpunkt aus Methode 1+2 festlegen
        line_endpoint: tuple | None = best_line or best_hline
        line_method = "Linie-V" if best_line else ("Linie-H" if best_hline else None)

        # --- Methode 3: Geknickte Fuehrungslinie (Pfad-Endpunkt) ---
        # Wenn noch kein Leitungsendpunkt gefunden: schwarze Pfade pruefen,
        # deren Punkte nahe dem Label liegen — dann den am weitesten entfernten
        # Punkt als Anlage-Position nehmen.
        if not line_endpoint:
            best_far_dist = 0.0
            for pts in line_paths:
                # Mindestens ein Punkt muss in der Naehe des Labels liegen
                near_label = any(
                    abs(px - cx) < TOLERANZ_LINIE * 3 and abs(py - cy) < 60
                    for px, py in pts
                )
                if not near_label:
                    continue
                # Den am weitesten entfernten Punkt als Anlagenpunkt nehmen
                for px, py in pts:
                    d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                    if d > best_far_dist:
                        best_far_dist = d
                        line_endpoint = (px, py)
                        line_method = "Linie-Pfad"

        # --- Methode 4: Symbol direkt am Leitungsendpunkt (30pt Radius) ---
        if line_endpoint:
            ex, ey = line_endpoint
            best_sym_dist = 30.0
            best_sym_at_line: tuple | None = None
            # Farb-Symbole bevorzugen (hoehere Praezision)
            for sx, sy in color_symbols:
                d = ((sx - ex) ** 2 + (sy - ey) ** 2) ** 0.5
                if d < best_sym_dist:
                    best_sym_dist = d
                    best_sym_at_line = (sx, sy)
            for sx, sy in symbol_centers:
                d = ((sx - ex) ** 2 + (sy - ey) ** 2) ** 0.5
                if d < best_sym_dist:
                    best_sym_dist = d
                    best_sym_at_line = (sx, sy)
            if best_sym_at_line:
                return best_sym_at_line, "Symbol-an-Linie"
            # Kein Symbol am Ende: Leitungsendpunkt selbst zurueckgeben
            return line_endpoint, line_method

        # --- Methode 5a: Gefuelltes Symbol in 150pt Radius ---
        best_dist = 150.0
        best_sym = None
        for sx, sy in symbol_centers:
            d = ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_sym = (sx, sy)
        if best_sym:
            return best_sym, "Symbol-gefuellt"

        # --- Methode 5b: Bauteil-Farb-Symbol in 200pt Radius ---
        best_dist = 200.0
        best_col = None
        for sx, sy in color_symbols:
            d = ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best_col = (sx, sy)
        if best_col:
            return best_col, "Symbol-Farbe"

        return None, "Fallback-Text"

    if on_progress:
        on_progress(30, f"{len(all_spans)} Spans, {len(vert_lines)} senkr./"
                    f"{len(horiz_lines)} waagr. Linien, {len(symbol_centers)} Symbole...")

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
            # Bauteil-Symbol suchen; Fallback: Textbox-Mitte
            sym, pos_method = _find_equipment_pos(span["cx"], span["cy"])
            entry = {
                "aks": aks_str,
                "beschreibung": span.get("block_description"),
                "pdf_x": round(sym[0] if sym else span["cx"], 1),
                "pdf_y": round(sym[1] if sym else span["cy"], 1),
                "pos_method": pos_method,
                "label_x": round(span["cx"], 1),
                "label_y": round(span["cy"], 1),
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
            sym, pos_method = _find_equipment_pos(span["cx"], span["cy"])
            ref = {
                "text": text,
                "pdf_x": round(sym[0] if sym else span["cx"], 1),
                "pdf_y": round(sym[1] if sym else span["cy"], 1),
                "pos_method": pos_method,
                "label_x": round(span["cx"], 1),
                "label_y": round(span["cy"], 1),
            }
            inline_match = re.search(r"Siehe Regelschema\s+(\w{2,}\d{2,})", text)
            if inline_match:
                ref["type"] = "inline"
                ref["anlage"] = inline_match.group(1)
            else:
                ref["type"] = "standalone"
                ref["anlage"] = None
            cross_references.append(ref)
            continue

        room_match = re.match(r"^((?:EG|KG|OG|DA|E|K|O)\.\d{3})(?:[-\s].*)?$", text)
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
            dy = span["y"] - ref["label_y"]
            dx = abs(span["cx"] - ref["label_x"])
            # Gleiche Zeile, nah am Label (max 120pt Abstand) — weit entfernte Spans ignorieren
            same_line_near = abs(dy) < 15 and 10 < dx < 120
            # Direkt unterhalb des Labels (enge Toleranz)
            below_label = 0 < dy < 35 and dx < 80
            if same_line_near or below_label:
                candidates.append(span)
        candidates.sort(key=lambda s: (abs(s["y"] - ref["label_y"]), abs(s["cx"] - ref["label_x"])))

        for cand in candidates:
            anlage_match = re.match(r"^(\w{2,}\d{2,})$", cand["text"])
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
                "label_x": round(span["cx"], 1),
                "label_y": round(span["cy"], 1),
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
