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

    # Bauteil-Position ermitteln:
    # 1. Fuehrungslinie (schwarz, ungefuellt) vom Label zur Komponente finden
    # 2. Am Endpunkt der Linie: farbig gefuellte Komponente suchen (Farbgruppen-Center)
    # 3. Fallback: naechste farbige Komponente zum Label

    # -- Schwarze Liniensegmente sammeln (aus items[] statt Bbox) --
    # Jedes Segment als (x0, y0, x1, y1) mit tatsaechlichen Pfad-Endpunkten
    black_segs: list[tuple[float, float, float, float]] = []
    # -- Farbig gefuellte Komponenten sammeln (non-gray, Flaeche > 1x1 pt) --
    # (center_x, center_y, x0, y0, x1, y1, fill_tuple)
    colored_comps: list[tuple[float, float, float, float, float, float, tuple]] = []

    for drawing in page.get_drawings():
        try:
            color = drawing.get("color")
            fill = drawing.get("fill")
            is_black = (
                color is not None
                and abs(color[0]) < 0.01 and abs(color[1]) < 0.01 and abs(color[2]) < 0.01
                and fill is None
            )

            if is_black:
                for seg in drawing.get("items", []):
                    if seg[0] != "l":
                        continue
                    p0, p1 = seg[1], seg[2]
                    seg_len = ((p1.x - p0.x) ** 2 + (p1.y - p0.y) ** 2) ** 0.5
                    if seg_len > 8:
                        black_segs.append((p0.x, p0.y, p1.x, p1.y))

            elif fill is not None:
                r = drawing["rect"]
                w = r.x1 - r.x0
                h = r.y1 - r.y0
                # Grau ausfiltern (alle 3 Kanaele ~gleich)
                is_gray = (
                    abs(fill[0] - fill[1]) < 0.05
                    and abs(fill[1] - fill[2]) < 0.05
                )
                if not is_gray and w > 1 and h > 1:
                    colored_comps.append((
                        (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2,
                        r.x0, r.y0, r.x1, r.y1,
                        fill,
                    ))

        except Exception as e:
            logger.warning("Fehler beim Lesen der Zeichnungsdaten: %s", e, exc_info=True)
            continue

    def _color_key(fill_tuple: tuple) -> tuple:
        """Farb-Schluessel fuer Gruppierung (auf 1 Dezimale gerundet)."""
        return (round(fill_tuple[0], 1), round(fill_tuple[1], 1), round(fill_tuple[2], 1))

    def _find_component_at(px: float, py: float, radius: float = 60.0) -> tuple | None:
        """Suche farbige Komponente an einem Punkt.

        Alle farbig gefuellten Elemente innerhalb des Radius werden nach Farbe
        gruppiert. Pro Gruppe wird die Gesamt-Bounding-Box berechnet und deren
        Mittelpunkt zurueckgegeben. Die Gruppe mit dem naechsten Mittelpunkt
        zum Suchpunkt gewinnt.

        Returns:
            (center_x, center_y, fill) oder None
        """
        nearby = [
            c for c in colored_comps
            if abs(c[0] - px) < radius and abs(c[1] - py) < radius
            and ((c[0] - px) ** 2 + (c[1] - py) ** 2) ** 0.5 < radius
        ]
        if not nearby:
            return None

        # Nach Farbe gruppieren, pro Gruppe Gesamt-Bbox-Center berechnen
        groups: dict[tuple, list] = {}
        for c in nearby:
            key = _color_key(c[6])
            if key not in groups:
                groups[key] = []
            groups[key].append(c)

        best_center = None
        best_dist = radius * 2
        best_fill = None
        for _key, comps in groups.items():
            min_x = min(c[2] for c in comps)
            min_y = min(c[3] for c in comps)
            max_x = max(c[4] for c in comps)
            max_y = max(c[5] for c in comps)
            gcx = (min_x + max_x) / 2
            gcy = (min_y + max_y) / 2
            gd = ((gcx - px) ** 2 + (gcy - py) ** 2) ** 0.5
            if gd < best_dist:
                best_dist = gd
                best_center = (gcx, gcy)
                best_fill = comps[0][6]

        if best_center:
            return (*best_center, best_fill)
        return None

    def _find_equipment_pos(
        cx: float, cy: float,
        bx0: float, by0: float, bx1: float, by1: float,
    ) -> tuple[tuple | None, str]:
        """Ermittelt Equipment-Position fuer eine AKS-Textbox.

        Strategie:
        1. Fuehrungslinie finden: schwarzes Segment das an der Label-Bbox-Kante
           startet (innerhalb 10pt). Das andere Ende ist der Leitungsendpunkt.
        2. Einfache Ketten-Verfolgung ab dem Endpunkt: verbundene schwarze
           Segmente folgen (max 5 Hops, nur in Richtung weg vom Label).
        3. Am finalen Endpunkt: farbige Komponente suchen (Farbgruppen-Center
           innerhalb 60pt Radius).
        4. Fallback: naechste farbige Komponente zum Label (200pt Radius).
        5. Letzter Fallback: Leitungsendpunkt oder Label-Mittelpunkt.

        Args:
            cx, cy: Label-Mittelpunkt
            bx0, by0, bx1, by1: Label-Bounding-Box

        Returns:
            (pos, method) — pos ist (x, y) oder None
        """
        # --- Schritt 1: Beste Fuehrungslinie finden ---
        # Schwarzes Segment dessen ein Endpunkt moeglichst nah an der Bbox-Kante
        # liegt (<10pt) und dessen anderer Endpunkt weiter vom Label-Center ist.
        best_seg_far = None         # (far_x, far_y)
        best_d_to_box = 10.0       # Toleranz: max 10pt von Bbox-Kante
        for sx0, sy0, sx1, sy1 in black_segs:
            for px, py, fx, fy in [(sx0, sy0, sx1, sy1), (sx1, sy1, sx0, sy0)]:
                # Abstand von (px,py) zur Bbox-Kante
                dx_box = max(bx0 - px, px - bx1, 0.0)
                dy_box = max(by0 - py, py - by1, 0.0)
                d_box = (dx_box ** 2 + dy_box ** 2) ** 0.5
                if d_box < best_d_to_box:
                    # Far-Punkt muss weiter vom Label sein als Near-Punkt
                    far_d = ((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5
                    near_d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                    if far_d > near_d:
                        best_d_to_box = d_box
                        best_seg_far = (fx, fy)

        # --- Schritt 2: Ketten-Verfolgung (max 5 Hops, Richtung weg vom Label) ---
        endpoint = best_seg_far
        if endpoint:
            epx, epy = endpoint
            dist_from_label = ((epx - cx) ** 2 + (epy - cy) ** 2) ** 0.5
            visited = {(round(epx, 0), round(epy, 0))}
            for _ in range(5):
                best_next = None
                best_conn_d = 10.0  # Max 10pt Verbindungstoleranz
                for sx0, sy0, sx1, sy1 in black_segs:
                    for px, py, fx, fy in [(sx0, sy0, sx1, sy1), (sx1, sy1, sx0, sy0)]:
                        conn_d = ((px - epx) ** 2 + (py - epy) ** 2) ** 0.5
                        if conn_d >= best_conn_d:
                            continue
                        fkey = (round(fx, 0), round(fy, 0))
                        if fkey in visited:
                            continue
                        # Muss weiter vom Label sein (oder min. gleich weit)
                        next_d = ((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5
                        if next_d >= dist_from_label - 5:
                            best_conn_d = conn_d
                            best_next = (fx, fy, fkey, next_d)
                if best_next:
                    epx, epy = best_next[0], best_next[1]
                    visited.add(best_next[2])
                    dist_from_label = best_next[3]
                    endpoint = (epx, epy)
                else:
                    break

        # --- Schritt 3: Farbige Komponente am Endpunkt suchen (60pt) ---
        if endpoint:
            result = _find_component_at(endpoint[0], endpoint[1], radius=60.0)
            if result:
                return (result[0], result[1]), "Symbol-an-Linie"
            return endpoint, "Linie"

        # --- Schritt 4: Fallback — naechste Komponente zum Label (200pt) ---
        result = _find_component_at(cx, cy, radius=200.0)
        if result:
            return (result[0], result[1]), "Symbol"

        return None, "Fallback-Text"

    if on_progress:
        on_progress(30, f"{len(all_spans)} Spans, {len(black_segs)} Linien-Segm./"
                    f"{len(colored_comps)} farb. Komp...")

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
            sym, pos_method = _find_equipment_pos(
                span["cx"], span["cy"],
                span["x"], span["y"], span["x2"], span["y2"],
            )
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
            sym, pos_method = _find_equipment_pos(
                span["cx"], span["cy"],
                span["x"], span["y"], span["x2"], span["y2"],
            )
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
