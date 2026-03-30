"""Erzeuge ein transparentes PDF-Overlay mit AKS-Koordinaten zur Qualitaetskontrolle.

Das Overlay kann in einem PDF-Viewer ueber den Grundrissplan gelegt werden.
Jeder AKS-Eintrag wird als farbiger Punkt + Kurztext an den ermittelten Koordinaten eingezeichnet.
Farbe zeigt die Erkennungsmethode:
  Linie-V         -> Blau
  Linie-H         -> Cyan
  Linie-Pfad      -> Hellblau (geknickte Fuehrungslinie, Pfad-Endpunkt)
  Symbol-an-Linie -> Dunkelgruen (Symbol direkt am Leitungsendpunkt)
  Symbol-gefuellt -> Gruen
  Symbol-Farbe    -> Orange
  Fallback-Text   -> Rot
  Schema (cross)  -> Lila
"""

from pathlib import Path

import fitz


# Farben nach Erkennungsmethode (RGB 0-1)
METHOD_COLORS = {
    "Linie-V":          (0.0, 0.4, 0.9),
    "Linie-H":          (0.0, 0.8, 0.9),
    "Linie-Pfad":       (0.4, 0.7, 1.0),
    "Symbol-an-Linie":  (0.0, 0.5, 0.1),
    "Symbol-gefuellt":  (0.0, 0.7, 0.2),
    "Symbol-Farbe":     (1.0, 0.5, 0.0),
    "Fallback-Text":    (0.9, 0.0, 0.0),
    "Schema":           (0.6, 0.0, 0.9),
}
DEFAULT_COLOR = (0.5, 0.5, 0.5)

PUNKT_RADIUS = 4.0   # pt
FONT_SIZE = 5.0      # pt


def generate_aks_overlay(
    registry_data: dict,
    source_pdf_path: str | Path,
    output_path: str | Path,
    on_progress: callable = None,
) -> str:
    """Erstellt ein PDF-Overlay mit AKS-Koordinaten zur Qualitaetskontrolle.

    Args:
        registry_data: Ergebnis von build_registry()
        source_pdf_path: Pfad zum Grundrissplan (fuer Seitengroesse)
        output_path: Pfad fuer das Overlay-PDF
        on_progress: Callback(progress_pct, message)

    Returns:
        Pfad zum erzeugten Overlay-PDF
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Seitengroesse aus Quell-PDF lesen
    src_doc = fitz.open(str(source_pdf_path))
    page_rect = src_doc[0].rect
    src_doc.close()

    # Neues leeres Dokument mit gleicher Seitengroesse
    doc = fitz.open()
    page = doc.new_page(width=page_rect.width, height=page_rect.height)

    equipment = registry_data.get("equipment", [])

    if on_progress:
        on_progress(10, f"Zeichne {len(equipment)} AKS-Eintraege...")

    for i, eq in enumerate(equipment):
        x = eq.get("pdf_x")
        y = eq.get("pdf_y")
        if x is None or y is None:
            continue

        method = eq.get("pos_method") or "Schema"
        color = METHOD_COLORS.get(method, DEFAULT_COLOR)

        # Farbiger Punkt an der Koordinate
        point_rect = fitz.Rect(
            x - PUNKT_RADIUS, y - PUNKT_RADIUS,
            x + PUNKT_RADIUS, y + PUNKT_RADIUS,
        )
        page.draw_circle(fitz.Point(x, y), PUNKT_RADIUS, color=color, fill=color)

        # Kurztext: letzten 2 AKS-Teile + Methode
        aks = eq.get("aks_parent", "")
        parts = aks.split("_")
        short_aks = "_".join(parts[-2:]) if len(parts) >= 2 else aks
        label = f"{short_aks}"

        page.insert_text(
            fitz.Point(x + PUNKT_RADIUS + 1, y + FONT_SIZE / 2),
            label,
            fontsize=FONT_SIZE,
            color=color,
        )

        if on_progress and i % 50 == 0:
            pct = 10 + int((i / len(equipment)) * 85)
            on_progress(pct, f"{i}/{len(equipment)} gezeichnet...")

    # Legende unten links
    legend_x = 10.0
    legend_y = page_rect.height - 10.0 - len(METHOD_COLORS) * 10.0
    page.insert_text(
        fitz.Point(legend_x, legend_y - 8),
        "Legende (Koordinaten-Quelle):",
        fontsize=6.0,
        color=(0, 0, 0),
    )
    for j, (method, color) in enumerate(METHOD_COLORS.items()):
        y_leg = legend_y + j * 10.0
        page.draw_circle(fitz.Point(legend_x + 3, y_leg), 3.0, color=color, fill=color)
        page.insert_text(
            fitz.Point(legend_x + 9, y_leg + 2),
            method,
            fontsize=6.0,
            color=color,
        )

    if on_progress:
        on_progress(98, "Speichere Overlay...")

    doc.save(str(output_path))
    doc.close()

    if on_progress:
        on_progress(100, "Overlay erstellt")

    return str(output_path)
