"""Facciata pubblica per l'uso come libreria da altri repository.

Un repo consumatore importa `dig` (o `search`) e passa una Config gia' costruita
(da profilo/YAML/override), senza conoscere i dettagli interni. Il client e'
iniettabile per i test; di default usa Internet Archive vero.
"""

from __future__ import annotations

from pathlib import Path

from .client import Client, InternetArchiveClient
from .config import Config
from .downloader import Downloader, DownloadReport, Estimate
from .manifest import Manifest
from .query import build_query


def _manifest_for(config: Config) -> Manifest:
    """Il manifest della run: quello configurato, o il default promesso.

    README e profili presentano il manifest (e il dedup MD5 seminato da li')
    come comportamento di base: senza un default, 'archivedigger run' seguito
    da 'export-manifest ./downloads/manifest.jsonl' esportava zero righe e il
    dedup tra run era inerte. Anche dry-run ed estimate lo LEGGONO (per il
    dedup seminato, cosi' l'anteprima combacia con la run reale), ma non vi
    scrivono: e' il Downloader a non registrare i record dry-run.
    """
    if config.download.manifest:
        return Manifest(config.download.manifest)
    return Manifest(Path(config.download.destdir) / "manifest.jsonl")


def dig(config: Config, client: Client | None = None) -> DownloadReport:
    """Esegue ricerca + download secondo la Config; ritorna il report."""
    client = client or InternetArchiveClient()
    return Downloader(client, config, manifest=_manifest_for(config)).run()


def estimate(config: Config, client: Client | None = None) -> Estimate:
    """Stima item/file/byte che il download produrrebbe, senza scaricare.

    Legge lo stesso manifest della run reale (per il dedup seminato), ma non
    vi scrive: la stima resta senza effetti collaterali.
    """
    client = client or InternetArchiveClient()
    return Downloader(client, config, manifest=_manifest_for(config)).estimate()


def search(config: Config, client: Client | None = None) -> list[str]:
    """Solo ricerca: ritorna la lista degli identifier che matchano la Config."""
    client = client or InternetArchiveClient()
    query = build_query(config.search)
    return list(
        client.search(query, sort=config.search.sort, max_items=config.search.max_items)
    )
