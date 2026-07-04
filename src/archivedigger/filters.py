"""Filtri file client-side, componibili come catena di strategy (D9, D10).

Ogni FileFilter riceve una lista di IAFile e ne restituisce un sottoinsieme.
Si applicano dopo la selezione di formato e prima del download. La catena
(`FilterChain`) li esegue in sequenza; `build_file_filter` la costruisce dalla
FiltersConfig, includendo solo i filtri effettivamente configurati.
"""

from __future__ import annotations

from typing import Protocol

from .config import FiltersConfig
from .models import IAFile
from .units import parse_duration, parse_size


class FileFilter(Protocol):
    def apply(self, files: list[IAFile]) -> list[IAFile]:
        ...


def _in_range(value, low, high) -> bool:
    """True se value e' entro [low, high]; estremi None = illimitati.

    value None (metrica ignota) non esclude mai: la decisione va al chiamante.
    """
    if value is None:
        return True
    if low is not None and value < low:
        return False
    return not (high is not None and value > high)


class DurationFilter:
    def __init__(self, min_duration=None, max_duration=None):
        self.min_duration = parse_duration(min_duration)
        self.max_duration = parse_duration(max_duration)

    def apply(self, files: list[IAFile]) -> list[IAFile]:
        return [f for f in files if _in_range(f.length, self.min_duration, self.max_duration)]


class FileSizeFilter:
    def __init__(self, min_size=None, max_size=None):
        self.min_size = parse_size(min_size)
        self.max_size = parse_size(max_size)

    def apply(self, files: list[IAFile]) -> list[IAFile]:
        return [f for f in files if _in_range(f.size, self.min_size, self.max_size)]


class Md5DedupFilter:
    """Scarta i file il cui MD5 e' gia' stato visto.

    Lo stato (gli MD5 gia' incontrati) puo' essere seminato dal manifest di una
    run precedente, cosi' il dedup persiste tra esecuzioni.
    """

    def __init__(self, seen: set[str] | None = None):
        self.seen: set[str] = set(seen or ())

    def apply(self, files: list[IAFile]) -> list[IAFile]:
        kept: list[IAFile] = []
        for f in files:
            if f.md5 is not None and f.md5 in self.seen:
                continue
            if f.md5 is not None:
                self.seen.add(f.md5)
            kept.append(f)
        return kept


class MaxFilesPerItemFilter:
    """Tiene al massimo N file per item (i primi N dopo gli altri filtri).

    Stateless per chiamata: `plan()` invoca `apply` una volta per item, quindi
    il cap vale per singolo item, non cumulativo sull'intero batch. Con N=1 si
    scarica un solo file per item (modalita' campionamento).
    """

    def __init__(self, limit: int):
        self.limit = limit

    def apply(self, files: list[IAFile]) -> list[IAFile]:
        return files[: self.limit]


class FilterChain:
    def __init__(self, filters: list[FileFilter]):
        self.filters = list(filters)

    def apply(self, files: list[IAFile]) -> list[IAFile]:
        for f in self.filters:
            files = f.apply(files)
        return files


def build_file_filter(config: FiltersConfig, seen_md5: set[str] | None = None) -> FilterChain:
    """Costruisce la catena dai soli filtri configurati nella FiltersConfig."""
    chain: list[FileFilter] = []
    if config.min_duration is not None or config.max_duration is not None:
        chain.append(DurationFilter(config.min_duration, config.max_duration))
    if config.min_file_size is not None or config.max_file_size is not None:
        chain.append(FileSizeFilter(config.min_file_size, config.max_file_size))
    if config.dedup:
        chain.append(Md5DedupFilter(seen_md5))
    if config.max_files_per_item is not None:
        chain.append(MaxFilesPerItemFilter(config.max_files_per_item))
    return FilterChain(chain)
