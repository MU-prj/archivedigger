"""Wrapper attorno alla libreria internetarchive.

E' l'unica superficie che parla con Internet Archive: search, lettura dei
metadati di un item, download di un singolo file. Il resto del package dipende
solo dal Protocol `Client`, non da internetarchive. Le funzioni della libreria
sono iniettabili, cosi' i test girano offline con fake e la libreria vera resta
non toccata.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

from .models import IAFile, IAItem


class Client(Protocol):
    def search(self, query: str, sort: str, max_items: int) -> Iterator[str]:
        ...

    def get_item(self, identifier: str) -> IAItem:
        ...

    def download_file(self, item: IAItem, file: IAFile, local_path: Path) -> None:
        ...


class InternetArchiveClient:
    def __init__(
        self,
        search_fn: Callable | None = None,
        get_item_fn: Callable | None = None,
    ):
        self._search_fn = search_fn
        self._get_item_fn = get_item_fn

    def _search_items(self):
        if self._search_fn is not None:
            return self._search_fn
        import internetarchive

        return internetarchive.search_items

    def _get_item(self):
        if self._get_item_fn is not None:
            return self._get_item_fn
        import internetarchive

        return internetarchive.get_item

    def search(
        self, query: str, sort: str = "downloads desc", max_items: int = 100
    ) -> Iterator[str]:
        sorts = [sort] if sort else None
        results = self._search_items()(query, fields=["identifier"], sorts=sorts)
        for i, row in enumerate(results):
            if max_items and i >= max_items:
                break
            yield row["identifier"]

    def get_item(self, identifier: str) -> IAItem:
        raw = self._get_item()(identifier)
        metadata = dict(getattr(raw, "metadata", {}) or {})
        files = [IAFile.from_dict(f) for f in getattr(raw, "files", []) or []]
        return IAItem(identifier=identifier, metadata=metadata, files=files)

    def download_file(self, item: IAItem, file: IAFile, local_path: Path) -> None:
        import shutil

        import internetarchive

        local_path.parent.mkdir(parents=True, exist_ok=True)
        internetarchive.download(
            item.identifier,
            files=[file.name],
            destdir=str(local_path.parent),
            no_directory=True,
            verbose=False,
        )
        # internetarchive scrive col nome IA (file.name) dentro destdir; il
        # layout puo' voler un basename diverso (es. flat: identifier__file).
        # Se differisce, sposto il file sul percorso scelto.
        parts = [p for p in file.name.split("/") if p not in ("", ".", "..")]
        landed = local_path.parent.joinpath(*parts) if parts else local_path
        if landed != local_path and landed.exists():
            shutil.move(str(landed), str(local_path))
            # rimuove le sottocartelle rimaste vuote (nomi IA con sottopercorsi)
            parent = landed.parent
            while parent != local_path.parent and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
