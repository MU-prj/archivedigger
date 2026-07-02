"""Parsing di dimensioni e durate leggibili dall'uomo.

Usato sia dai filtri di ricerca (item_size) sia dai filtri file client-side
(dimensione e durata dei singoli file), cosi' l'utente puo' scrivere "500M" o
"1:30" in YAML e sulla CLI invece di byte e secondi grezzi.
"""

from __future__ import annotations

_SIZE_UNITS = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
    "T": 1024**4,
    "TB": 1024**4,
}


def parse_size(value: str | int | None) -> int | None:
    """Converte una dimensione leggibile ("500K", "10M", "2G") in byte.

    Accetta anche interi o stringhe numeriche (byte) e None (passthrough).
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().upper()
    if not text:
        raise ValueError("Dimensione vuota")
    num = text
    unit = ""
    for i, ch in enumerate(text):
        if not (ch.isdigit() or ch in ".,"):
            num, unit = text[:i], text[i:]
            break
    unit = unit.strip()
    if unit not in _SIZE_UNITS:
        raise ValueError(f"Unita' di dimensione sconosciuta: {value!r}")
    try:
        magnitude = float(num.replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"Dimensione non valida: {value!r}") from exc
    return int(magnitude * _SIZE_UNITS[unit])


def parse_duration(value: str | int | float | None) -> float | None:
    """Converte una durata in secondi.

    Accetta secondi (int/float/str numerica) o formato orologio "mm:ss" /
    "hh:mm:ss". None passa attraverso.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if ":" in text:
        parts = text.split(":")
        if not all(parts):
            raise ValueError(f"Durata non valida: {value!r}")
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
        return seconds
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Durata non valida: {value!r}") from exc
