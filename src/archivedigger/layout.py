"""DiskLayout: strategy che decidono il percorso locale di ogni file (D14).

- FlatLayout:       destdir/<identifier>__<file>            (default)
- CollectionLayout: destdir/<collection>/<identifier>/<file>
- ItemLayout:       destdir/<identifier>/<file>

FlatLayout mette tutto in un'unica cartella: prefissa il nome file con
l'identifier (e appiattisce eventuali sottocartelle) per evitare collisioni tra
item diversi con file omonimi. Categorizzare in sottocartelle e' opzionale
(collection/item).

Se un item non ha collezione, CollectionLayout ripiega sul solo identifier.
I nomi file di IA possono contenere sottocartelle ("/"): CollectionLayout e
ItemLayout le preservano, FlatLayout le appiattisce con "__".
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from .config import DownloadConfig
from .models import IAFile, IAItem

_ILLEGAL = re.compile(r'[<>:"\\|?*]')


def _safe(component: str) -> str:
    """Ripulisce un singolo componente di percorso dai caratteri illegali."""
    return _ILLEGAL.sub("_", component).strip() or "_"


def _rel_name(name: str) -> Path:
    # I nomi IA usano '/' come separatore anche su Windows.
    parts = [_safe(p) for p in name.split("/") if p not in ("", ".", "..")]
    return Path(*parts) if parts else Path("_")


class DiskLayout(Protocol):
    def path_for(self, destdir: Path, item: IAItem, file: IAFile) -> Path:
        ...


class CollectionLayout:
    def path_for(self, destdir: Path, item: IAItem, file: IAFile) -> Path:
        base = destdir
        if item.primary_collection:
            base = base / _safe(item.primary_collection)
        return base / _safe(item.identifier) / _rel_name(file.name)


class ItemLayout:
    def path_for(self, destdir: Path, item: IAItem, file: IAFile) -> Path:
        return destdir / _safe(item.identifier) / _rel_name(file.name)


class FlatLayout:
    def path_for(self, destdir: Path, item: IAItem, file: IAFile) -> Path:
        parts = [_safe(p) for p in file.name.split("/") if p not in ("", ".", "..")]
        flat = "__".join(parts) if parts else "_"
        return destdir / f"{_safe(item.identifier)}__{flat}"


_LAYOUTS: dict[str, type[DiskLayout]] = {
    "collection": CollectionLayout,
    "item": ItemLayout,
    "flat": FlatLayout,
}


def build_layout(download: DownloadConfig) -> DiskLayout:
    name = download.layout
    if name not in _LAYOUTS:
        available = ", ".join(sorted(_LAYOUTS))
        raise ValueError(f"Layout sconosciuto: {name!r}. Disponibili: {available}")
    return _LAYOUTS[name]()
