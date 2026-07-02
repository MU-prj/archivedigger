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
        """Costruisce da un dict di metadati file di internetarchive."""
        from .units import parse_duration

        size = data.get("size")
        return cls(
            name=data.get("name", ""),
            format=data.get("format"),
            size=int(size) if size is not None else None,
            md5=data.get("md5"),
            length=parse_duration(data.get("length")),
            source=data.get("source"),
        )


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
