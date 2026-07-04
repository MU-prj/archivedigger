"""Strategy di selezione formato: quali file di un item scaricare.

Due strategie intercambiabili (D8):
- ExactFormatStrategy: tiene tutti i file che matchano una lista esatta di
  formati (e/o pattern glob).
- PreferenceChainStrategy: catena di gruppi a preferenza decrescente; per ogni
  item scarica solo i file del primo gruppo disponibile (evita duplicati dello
  stesso brano in formati diversi). I formati dentro un gruppo sono a pari merito.

`FileSelection` compone la selezione completa dalla FilesConfig: prima i
criteri per-file (source, glob, exclude_glob), poi la strategy di formato.
L'ordine conta: filtrare per source PRIMA della catena di preferenza fa si'
che la catena scelga il miglior formato tra i soli file ammessi.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Protocol

from .config import FilesConfig
from .models import IAFile


class FormatStrategy(Protocol):
    def select(self, files: list[IAFile]) -> list[IAFile]:
        ...


class ExactFormatStrategy:
    def __init__(self, formats: list[str] | None = None):
        self.formats = list(formats or [])

    def select(self, files: list[IAFile]) -> list[IAFile]:
        if not self.formats:
            return list(files)
        wanted = set(self.formats)
        return [f for f in files if f.format in wanted]


class PreferenceChainStrategy:
    def __init__(self, prefer: list[list[str]]):
        self.prefer = [list(group) for group in prefer]

    def select(self, files: list[IAFile]) -> list[IAFile]:
        for group in self.prefer:
            wanted = set(group)
            matched = [f for f in files if f.format in wanted]
            if matched:
                return matched
        return []


def build_format_strategy(files: FilesConfig) -> FormatStrategy:
    """Sceglie la strategy in base alla FilesConfig.

    prefer ha la precedenza (catena); altrimenti filtro esatto per formati;
    in assenza di entrambi, tiene tutti i file.
    """
    if files.prefer:
        return PreferenceChainStrategy(files.prefer)
    return ExactFormatStrategy(files.formats)


SOURCE_MODES = ("any", "original", "derivative")


def _glob_match(name: str, pattern: str) -> bool:
    # match deterministico e case-insensitive: le estensioni su IA arrivano
    # in ogni combinazione di maiuscole ('Track01.FLAC' deve matchare
    # '*.flac'), e fnmatch.fnmatch cambierebbe semantica per piattaforma
    return fnmatchcase(name.lower(), pattern.lower())


class FileSelection:
    """Selezione completa dei file di un item a partire dalla FilesConfig.

    Applica in ordine: filtro source (original/derivative), glob di inclusione,
    glob di esclusione, poi la strategy di formato. Un file senza `source`
    dichiarato non viene mai escluso dal filtro source (coerente con la
    filosofia dei filtri: metrica ignota = decisione rimandata).
    """

    def __init__(self, files: FilesConfig):
        if files.source not in SOURCE_MODES:
            available = ", ".join(SOURCE_MODES)
            raise ValueError(
                f"Source sconosciuto: {files.source!r}. Disponibili: {available}"
            )
        self.source = files.source
        self.glob = files.glob
        self.exclude_glob = files.exclude_glob
        self.format_strategy = build_format_strategy(files)

    def select(self, files: list[IAFile]) -> list[IAFile]:
        admitted = [f for f in files if self._admits(f)]
        return self.format_strategy.select(admitted)

    def _admits(self, f: IAFile) -> bool:
        if self.source != "any" and f.source is not None and f.source != self.source:
            return False
        if self.glob and not _glob_match(f.name, self.glob):
            return False
        return not (self.exclude_glob and _glob_match(f.name, self.exclude_glob))


def build_file_selection(files: FilesConfig) -> FileSelection:
    """Punto d'ingresso usato dal Downloader: FilesConfig -> selezione file."""
    return FileSelection(files)
