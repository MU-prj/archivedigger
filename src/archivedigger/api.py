"""Facciata pubblica per l'uso come libreria da altri repository.

Un repo consumatore importa `dig` (o `search`) e passa una Config gia' costruita
(da profilo/YAML/override), senza conoscere i dettagli interni. Il client e'
iniettabile per i test; di default usa Internet Archive vero.
"""

from __future__ import annotations

from .client import Client, InternetArchiveClient
from .config import Config
from .downloader import Downloader, DownloadReport
from .manifest import Manifest
from .query import build_query


def dig(config: Config, client: Client | None = None) -> DownloadReport:
    """Esegue ricerca + download secondo la Config; ritorna il report."""
    client = client or InternetArchiveClient()
    manifest = Manifest(config.download.manifest) if config.download.manifest else None
    return Downloader(client, config, manifest=manifest).run()


def search(config: Config, client: Client | None = None) -> list[str]:
    """Solo ricerca: ritorna la lista degli identifier che matchano la Config."""
    client = client or InternetArchiveClient()
    query = build_query(config.search)
    return list(
        client.search(query, sort=config.search.sort, max_items=config.search.max_items)
    )
