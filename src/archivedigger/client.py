"""Wrapper attorno alla libreria internetarchive.

E' l'unica superficie che parla con Internet Archive: search, lettura dei
metadati di un item, download di un singolo file. Il resto del package dipende
solo dal Protocol `Client`, non da internetarchive. Le funzioni della libreria
sono iniettabili, cosi' i test girano offline con fake e la libreria vera resta
non toccata.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from itertools import islice
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
        # max_items=0 o None = illimitato (comportamento asserito dai test)
        for row in islice(iter(results), max_items or None):
            identifier = row.get("identifier")
            if identifier is None:
                # su errore l'API scrape emette una riga {'error': ...}: farla
                # esplodere come KeyError maschererebbe il messaggio vero
                raise ValueError(f"Ricerca IA fallita: {row.get('error', row)!r}")
            yield identifier

    def get_item(self, identifier: str) -> IAItem:
        raw = self._get_item()(identifier)
        metadata = dict(getattr(raw, "metadata", {}) or {})
        files = [IAFile.from_dict(f) for f in getattr(raw, "files", []) or []]
        return IAItem(identifier=identifier, metadata=metadata, files=files)

    def download_file(self, item: IAItem, file: IAFile, local_path: Path) -> None:
        """Scarica un singolo file in una staging directory usa-e-getta.

        Scaricare direttamente in destdir aveva tre difetti: (1) file di item
        diversi con lo stesso basename atterravano sullo stesso percorso
        provvisorio, corrompendosi a vicenda con workers > 1; (2) la libreria
        salta in silenzio i file locali con dimensione/mtime combacianti,
        vanificando resume=force e la riparazione dei corrotti; (3) un
        download a vuoto (item oscurato, nome non piu' esistente) non alzava
        errori e veniva registrato come scaricato. La staging directory vuota
        e per-chiamata elimina (1) e (2); la verifica dell'atterraggio
        elimina (3).
        """
        import os
        import shutil
        import tempfile

        import internetarchive

        local_path.parent.mkdir(parents=True, exist_ok=True)
        staging = tempfile.mkdtemp(prefix=".staging-", dir=local_path.parent)
        try:
            internetarchive.download(
                item.identifier,
                files=[file.name],
                destdir=staging,
                no_directory=True,
                verbose=False,
                # i retry con backoff sono del Downloader: qui il minimo
                # possibile (la libreria coercisce 0 al default con
                # 'retries = retries or 2', quindi 1 e' il pavimento)
                retries=1,
            )
            landed = [p for p in Path(staging).rglob("*") if p.is_file()]
            if not landed:
                raise FileNotFoundError(
                    f"{item.identifier}/{file.name}: la libreria non ha "
                    "scaricato nulla (item oscurato o nome file inesistente?)"
                )
            # os.replace (stesso filesystem: staging vive in destdir) e' atomico
            # e fallisce forte se local_path e' una directory — shutil.move
            # sposterebbe il file DENTRO la directory, registrando un percorso
            # sbagliato come 'downloaded'
            os.replace(landed[0], local_path)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
