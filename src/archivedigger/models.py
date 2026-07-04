"""Modelli di dominio disaccoppiati dalla libreria internetarchive.

Le strategy (formati, filtri file) operano su questi tipi, non sui dict grezzi
di internetarchive: cosi' i test girano offline con dati finti e il resto del
codice non dipende dalla forma interna della libreria.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class IAFile:
    """Un file appartenente a un item di Internet Archive."""

    name: str
    format: str | None = None
    size: int | None = None
    md5: str | None = None
    length: float | None = None  # durata in secondi, quando presente
    source: str | None = None  # 'original' | 'derivative'

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IAFile:
        """Costruisce da un dict di metadati file di internetarchive.

        I metadati di IA sono sporchi: campi che arrivano come lista
        (si prende il primo valore) o non parsabili (diventano None,
        metrica ignota: la decisione passa alla catena di filtri).
        Un file illeggibile non deve far crollare l'intero plan().
        """
        from .units import parse_duration

        # anche i campi stringa arrivano sporchi: un 'format' lista (tag
        # ripetuto in files.xml) sarebbe unhashable nei set delle strategy
        return cls(
            name=_lenient(str, data.get("name")) or "",
            format=_lenient(str, data.get("format")),
            size=_lenient(int, data.get("size")),
            md5=_lenient(str, data.get("md5")),
            length=_lenient(parse_duration, data.get("length")),
            source=_lenient(str, data.get("source")),
        )


def _lenient(parse, value):
    """Applica `parse` a un metadato sporco: liste → primo elemento,
    valori mancanti o non parsabili → None."""
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    try:
        return parse(value)
    except (ValueError, TypeError):
        return None


@dataclass
class IAItem:
    """Un item di Internet Archive: identifier, metadati e file."""

    identifier: str
    metadata: dict[str, Any]
    files: list[IAFile]

    @property
    def primary_collection(self) -> str | None:
        coll = self.metadata.get("collection")
        if isinstance(coll, list):
            return coll[0] if coll else None
        return coll
