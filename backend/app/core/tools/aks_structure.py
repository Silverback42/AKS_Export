"""AKS-Schluessel Referenztabellen.

Zentrale Definition aller bekannten AKS-Codes (Gewerke, Ebenen,
Betriebsmittel, MSR-Funktionscodes) gemaess AKS-Schluesselschema.
"""

# Stelle 9: Gewerk (Einzelbuchstabe)
GEWERK_CODES: dict[str, str] = {
    "A": "Automatisierung",
    "F": "Hallenkrane",
    "G": "Brandmeldung",
    "H": "Heizung",
    "L": "Lueftung",
    "N": "Betriebssicherung",
    "W": "Waermepumpen",
    "Y": "Sonstiges",
    "Z": "Regelung",
}

# Stellen 22-23: Ebene
EBENE_CODES: dict[str, str] = {
    "EG": "Erdgeschoss",
    "KG": "Kellergeschoss",
    "OG": "Obergeschoss",
    "DA": "Dach",
}

# Ebene-Prefix fuer lesbare Raumnummer (z.B. EG441 -> E.441)
EBENE_PREFIX: dict[str, str] = {
    "EG": "E",
    "KG": "K",
    "OG": "O",
    "DA": "DA",
}

# Stelle 26: Betriebsmittel-Typ
BETRIEBSMITTEL_CODES: dict[str, str] = {
    "E": "Leuchte",
    "M": "Motor/Ventil",
    "S": "Sensor/Schalter",
    "B": "Sensor",
    "A": "Aktor",
    "U": "Zaehler",
    "Q": "Zaehler",
    "F": "Sicherheit/Frost",
    "PF": "Pruefeinrichtung",
}

# Stellen 29-30: MSR-Funktionscodes (nur bei MSR-Geraeten)
MSR_FUNKTIONSCODES: dict[str, str] = {
    "BM": "Betriebsmeldung",
    "FR": "Frostschutz",
    "GM": "Grenzwertmeldung",
    "HD": "Handsteuerung",
    "MW": "Messwert",
    "SM": "Stellungsmeldung",
    "ST": "Steuersignal",
    "SW": "Sollwert",
    "RW": "Rueckmeldewert",
    "SB": "Statusbit",
    "RM": "Rueckmeldung",
    "WM": "Waermemenge",
    "NC": "Netzfuehrung",
    "ZP": "Zustandsspeicher",
    "AF": "Anforderung",
    "EE": "Ein-/Ausschalter",
    "TR": "Treiber",
    "MV": "Magnetventil",
}

# Kombinierte Geraet-Type-Map (Betriebsmittel + MSR)
DEFAULT_GERAET_TYPE_MAP: dict[str, str] = {
    **BETRIEBSMITTEL_CODES,
    **MSR_FUNKTIONSCODES,
}
