"""Costruzione della query Lucene per la ricerca item-level su Internet Archive.

Ogni famiglia di filtri e' una `SearchFilter` (strategy): riceve la SearchConfig
e restituisce zero o piu' clausole Lucene. `build_query` le compone in AND.
Una filter che non ha nulla da dire restituisce lista vuota: nessuna clausola,
quindi nessuna restrizione (coerente con "nessun filtro = tutto").
"""

from __future__ import annotations

from typing import Protocol

from .config import SearchConfig
from .units import parse_size


class SearchFilter(Protocol):
    def clauses(self, search: SearchConfig) -> list[str]:
        ...


def _quote(value: str) -> str:
    """Racchiude tra virgolette i valori con spazi (richiesto da Lucene)."""
    text = str(value)
    return f'"{text}"' if " " in text else text


def _or_group(field: str, values: list[str]) -> list[str]:
    if not values:
        return []
    quoted = [_quote(v) for v in values]
    if len(quoted) == 1:
        return [f"{field}:{quoted[0]}"]
    return [f"{field}:({' OR '.join(quoted)})"]


def _term(field: str, value: str | None) -> list[str]:
    if value is None:
        return []
    return [f"{field}:{_quote(value)}"]


def _range(field: str, low: object | None, high: object | None) -> list[str]:
    if low is None and high is None:
        return []
    lo = "*" if low is None else low
    hi = "*" if high is None else high
    return [f"{field}:[{lo} TO {hi}]"]


class MediatypeFilter:
    def clauses(self, search: SearchConfig) -> list[str]:
        return _or_group("mediatype", list(search.mediatype))


class CollectionFilter:
    def clauses(self, search: SearchConfig) -> list[str]:
        return _or_group("collection", list(search.collection))


class TextFilter:
    """Campi testuali a valore singolo (creator, title, description, language)."""

    def clauses(self, search: SearchConfig) -> list[str]:
        out: list[str] = []
        out += _term("creator", search.creator)
        out += _term("title", search.title)
        out += _term("description", search.description)
        out += _term("language", search.language)
        return out


class SubjectFilter:
    def clauses(self, search: SearchConfig) -> list[str]:
        return _or_group("subject", list(search.subject))


class DateRangeFilter:
    """Range temporali: data del contenuto, anno, data di upload su IA."""

    def clauses(self, search: SearchConfig) -> list[str]:
        out: list[str] = []
        out += _range("date", search.date_from, search.date_to)
        out += _range("year", search.year_from, search.year_to)
        out += _range("addeddate", search.added_after, search.added_before)
        return out


# Preset licenza -> pattern Lucene su licenseurl.
_LICENSE_PRESETS: dict[str, str] = {
    "any": "",
    "publicdomain": "licenseurl:(*publicdomain*)",
    "cc": "licenseurl:(*creativecommons.org/licenses/*)",
    "cc-commercial": "licenseurl:(*creativecommons.org/licenses/*) AND NOT licenseurl:*nc*",
}


class LicenseFilter:
    """Diritti d'uso: preset su licenseurl, oppure un URL di licenza esatto.

    `license_url` esplicito ha la precedenza sul preset.
    """

    def clauses(self, search: SearchConfig) -> list[str]:
        if search.license_url is not None:
            return [f'licenseurl:"{search.license_url}"']
        preset = search.license
        if preset not in _LICENSE_PRESETS:
            available = ", ".join(sorted(_LICENSE_PRESETS))
            raise ValueError(
                f"Preset di license sconosciuto: {preset!r}. Disponibili: {available}"
            )
        clause = _LICENSE_PRESETS[preset]
        return [clause] if clause else []


class PopularityFilter:
    """Range numerici: download, valutazione media, dimensione totale item."""

    def clauses(self, search: SearchConfig) -> list[str]:
        out: list[str] = []
        out += _range("downloads", search.min_downloads, search.max_downloads)
        out += _range("avg_rating", search.min_rating, None)
        out += _range(
            "item_size",
            parse_size(search.min_item_size),
            parse_size(search.max_item_size),
        )
        return out


class RawQueryFilter:
    """Via di fuga: aggiunge una query Lucene grezza scritta dall'utente."""

    def clauses(self, search: SearchConfig) -> list[str]:
        if not search.query:
            return []
        return [f"({search.query})"]


DEFAULT_FILTERS: list[SearchFilter] = [
    MediatypeFilter(),
    CollectionFilter(),
    TextFilter(),
    SubjectFilter(),
    DateRangeFilter(),
    LicenseFilter(),
    PopularityFilter(),
    RawQueryFilter(),
]


def build_query(search: SearchConfig, filters: list[SearchFilter] | None = None) -> str:
    active = DEFAULT_FILTERS if filters is None else filters
    clauses: list[str] = []
    for f in active:
        clauses.extend(f.clauses(search))
    return " AND ".join(clauses)
