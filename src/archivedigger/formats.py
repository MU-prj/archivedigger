"""Strategy di selezione formato: quali file di un item scaricare.

Due strategie intercambiabili (D8):
- ExactFormatStrategy: tiene tutti i file che matchano una lista esatta di
  formati (e/o pattern glob).
- PreferenceChainStrategy: catena di gruppi a preferenza decrescente; per ogni
  item scarica solo i file del primo gruppo disponibile (evita duplicati dello
  stesso brano in formati diversi). I formati dentro un gruppo sono a pari merito.
"""

from __future__ import annotations

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
