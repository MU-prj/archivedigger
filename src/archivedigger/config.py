"""Configurazione di archivedigger.

La config e' strutturata in quattro sezioni (search, files, filters, download)
e viene costruita per stratificazione con precedenza crescente:

    default del package  <  profilo preset  <  job YAML  <  override CLI

Ogni livello e' un dizionario parziale: i campi omessi ricadono sul livello
sottostante. `Config.build()` e' il punto d'ingresso usato sia dalla CLI sia
dall'API libreria.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from importlib import resources
from typing import Any

import yaml


@dataclass
class SearchConfig:
    mediatype: list[str] = field(default_factory=lambda: ["audio", "etree"])
    collection: list[str] = field(default_factory=list)
    creator: str | None = None
    title: str | None = None
    subject: list[str] = field(default_factory=list)
    description: str | None = None
    language: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    added_after: str | None = None
    added_before: str | None = None
    license: str = "any"
    license_url: str | None = None
    min_downloads: int | None = None
    max_downloads: int | None = None
    min_item_size: str | None = None
    max_item_size: str | None = None
    min_rating: float | None = None
    query: str | None = None
    sort: str = "downloads desc"
    max_items: int = 100


@dataclass
class FilesConfig:
    formats: list[str] = field(default_factory=list)
    prefer: list[list[str]] = field(default_factory=list)
    glob: str | None = None
    exclude_glob: str | None = None
    source: str = "any"  # any | original | derivative


@dataclass
class FiltersConfig:
    min_duration: float | None = None
    max_duration: float | None = None
    min_file_size: str | None = None
    max_file_size: str | None = None
    dedup: bool = False
    max_files_per_item: int | None = None


@dataclass
class DownloadConfig:
    destdir: str = "./downloads"
    layout: str = "flat"
    workers: int = 4
    retries: int = 3
    resume: str = "checksum"
    ignore_errors: bool = True
    size_budget_gb: float | None = None
    dry_run: bool = False
    manifest: str | None = None


_SECTIONS: dict[str, type] = {
    "search": SearchConfig,
    "files": FilesConfig,
    "filters": FiltersConfig,
    "download": DownloadConfig,
}


@dataclass
class Config:
    search: SearchConfig = field(default_factory=SearchConfig)
    files: FilesConfig = field(default_factory=FilesConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    profile: str | None = None

    @classmethod
    def build(
        cls,
        profile: str | None = None,
        job: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> Config:
        """Costruisce una Config stratificando i livelli in ordine di precedenza."""
        merged: dict[str, Any] = {}
        if profile is not None:
            _merge_layer(merged, load_profile(profile))
            merged["profile"] = profile
        if job is not None:
            _merge_layer(merged, job)
        if overrides is not None:
            _merge_layer(merged, overrides)
        return cls.from_dict(merged)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Costruisce una Config da un dizionario gia' fuso (sezioni parziali)."""
        unknown = set(data) - set(_SECTIONS) - {"profile"}
        if unknown:
            available = ", ".join(_SECTIONS)
            raise ValueError(
                f"Sezioni sconosciute: {', '.join(sorted(unknown))}. "
                f"Disponibili: {available}"
            )
        kwargs: dict[str, Any] = {}
        for name, section_cls in _SECTIONS.items():
            section_data = data.get(name) or {}
            kwargs[name] = _build_section(section_cls, section_data)
        if "profile" in data:
            kwargs["profile"] = data["profile"]
        return cls(**kwargs)


def _build_section(section_cls: type, data: dict[str, Any]):
    known = {f.name for f in fields(section_cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(
            f"Campi sconosciuti per {section_cls.__name__}: {', '.join(sorted(unknown))}"
        )
    # In YAML e' naturale scrivere un valore singolo dove il campo e' una lista
    # (collection: librivoxaudio): senza coercizione, list("stringa") a valle
    # esploderebbe il valore in caratteri. Idem per i gruppi di prefer scritti
    # piatti (prefer: [Flac, VBR MP3] invece di liste annidate).
    coerced = {
        key: _coerce_list_shapes(_field_type(section_cls, key), value)
        for key, value in data.items()
    }
    return section_cls(**coerced)


def _field_type(section_cls: type, name: str) -> str | None:
    # Le annotazioni sono stringhe (from __future__ import annotations).
    return next((f.type for f in fields(section_cls) if f.name == name), None)


def _coerce_list_shapes(field_type: str | None, value: Any) -> Any:
    if field_type == "list[str]" and isinstance(value, str):
        return [value]
    if field_type == "list[list[str]]":
        if isinstance(value, str):
            return [[value]]
        if isinstance(value, list):
            return [[g] if isinstance(g, str) else g for g in value]
    return value


def _merge_layer(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    """Fonde un livello di config e risolve i campi mutuamente esclusivi."""
    _deep_merge(base, overlay)
    # formats e prefer sono modi ALTERNATIVI di selezione: un livello che ne
    # sceglie esplicitamente uno azzera l'altro ereditato dai livelli sotto,
    # altrimenti '--formats "VBR MP3"' su un profilo con prefer verrebbe
    # ignorato in silenzio (prefer ha la precedenza nella strategy).
    files = overlay.get("files")
    if not isinstance(files, dict):  # sezione malformata: lo dira' from_dict
        return
    if files.get("formats") and not files.get("prefer"):
        base["files"]["prefer"] = []
    elif files.get("prefer") and not files.get("formats"):
        base["files"]["formats"] = []


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    """Fonde `overlay` dentro `base` in-place, sezione per sezione.

    I valori esplicitamente None vengono ignorati (non azzerano il livello
    sottostante): serve perche' i template YAML dichiarano i campi come null.
    """
    for key, value in overlay.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        elif isinstance(value, dict):
            base[key] = dict(value)
        else:
            base[key] = value


def load_profile(name: str) -> dict[str, Any]:
    """Carica un profilo preset YAML incluso nel package."""
    resource = resources.files("archivedigger.profiles").joinpath(f"{name}.yaml")
    if not resource.is_file():
        available = ", ".join(list_profiles())
        raise ValueError(f"Profilo sconosciuto: {name!r}. Disponibili: {available}")
    data = yaml.safe_load(resource.read_text(encoding="utf-8")) or {}
    data.pop("profile", None)  # metadato del file, non un campo di config
    return data


def list_profiles() -> list[str]:
    """Elenca i profili preset disponibili nel package."""
    root = resources.files("archivedigger.profiles")
    return sorted(
        p.name[: -len(".yaml")]
        for p in root.iterdir()
        if p.name.endswith(".yaml")
    )
