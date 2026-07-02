"""Interfaccia a riga di comando di archivedigger (argparse, zero dipendenze).

Ogni flag corrisponde a un campo di Config e sovrascrive job YAML e profilo.
`args_to_overrides` costruisce il dizionario di override includendo solo le
flag effettivamente passate dall'utente (le altre restano ai livelli sotto).

Sottocomandi: run, search, estimate, export-manifest, profiles.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from .client import Client
from .config import Config, list_profiles

# Mappa: nome attributo argparse -> (sezione, campo). Solo i campi non-None
# finiscono negli override, cosi' cio' che l'utente non passa non azzera nulla.
_SCALAR_MAP: dict[str, tuple[str, str]] = {
    "query": ("search", "query"),
    "creator": ("search", "creator"),
    "title": ("search", "title"),
    "description": ("search", "description"),
    "language": ("search", "language"),
    "date_from": ("search", "date_from"),
    "date_to": ("search", "date_to"),
    "year_from": ("search", "year_from"),
    "year_to": ("search", "year_to"),
    "added_after": ("search", "added_after"),
    "added_before": ("search", "added_before"),
    "license": ("search", "license"),
    "license_url": ("search", "license_url"),
    "min_downloads": ("search", "min_downloads"),
    "max_downloads": ("search", "max_downloads"),
    "min_item_size": ("search", "min_item_size"),
    "max_item_size": ("search", "max_item_size"),
    "min_rating": ("search", "min_rating"),
    "sort": ("search", "sort"),
    "max_items": ("search", "max_items"),
    "glob": ("files", "glob"),
    "exclude_glob": ("files", "exclude_glob"),
    "source": ("files", "source"),
    "min_duration": ("filters", "min_duration"),
    "max_duration": ("filters", "max_duration"),
    "min_file_size": ("filters", "min_file_size"),
    "max_file_size": ("filters", "max_file_size"),
    "destdir": ("download", "destdir"),
    "layout": ("download", "layout"),
    "workers": ("download", "workers"),
    "retries": ("download", "retries"),
    "resume": ("download", "resume"),
    "size_budget_gb": ("download", "size_budget_gb"),
    "manifest": ("download", "manifest"),
}

# Flag lista (ripetibili) -> (sezione, campo).
_LIST_MAP: dict[str, tuple[str, str]] = {
    "mediatype": ("search", "mediatype"),
    "collection": ("search", "collection"),
    "subject": ("search", "subject"),
    "formats": ("files", "formats"),
}


def parse_prefer(spec: str) -> list[list[str]]:
    """Interpreta "Flac=AIFF=WAVE>VBR MP3" -> [[Flac,AIFF,WAVE],[VBR MP3]].

    '>' separa i gruppi in ordine di preferenza; '=' i formati a pari merito.
    """
    groups: list[list[str]] = []
    for group in spec.split(">"):
        members = [m.strip() for m in group.split("=") if m.strip()]
        if members:
            groups.append(members)
    return groups


def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile")
    # ricerca
    p.add_argument("--query")
    p.add_argument("--mediatype", action="append")
    p.add_argument("--collection", action="append")
    p.add_argument("--creator")
    p.add_argument("--title")
    p.add_argument("--subject", action="append")
    p.add_argument("--description")
    p.add_argument("--language")
    p.add_argument("--date-from", dest="date_from")
    p.add_argument("--date-to", dest="date_to")
    p.add_argument("--year-from", dest="year_from", type=int)
    p.add_argument("--year-to", dest="year_to", type=int)
    p.add_argument("--added-after", dest="added_after")
    p.add_argument("--added-before", dest="added_before")
    p.add_argument("--license")
    p.add_argument("--license-url", dest="license_url")
    p.add_argument("--min-downloads", dest="min_downloads", type=int)
    p.add_argument("--max-downloads", dest="max_downloads", type=int)
    p.add_argument("--min-item-size", dest="min_item_size")
    p.add_argument("--max-item-size", dest="max_item_size")
    p.add_argument("--min-rating", dest="min_rating", type=float)
    p.add_argument("--sort")
    p.add_argument("--max-items", dest="max_items", type=int)
    # file
    p.add_argument("--formats", action="append")
    p.add_argument("--prefer")
    p.add_argument("--glob")
    p.add_argument("--exclude-glob", dest="exclude_glob")
    p.add_argument("--source", choices=["original", "derivative"])
    # filtri file
    p.add_argument("--min-duration", dest="min_duration")
    p.add_argument("--max-duration", dest="max_duration")
    p.add_argument("--min-file-size", dest="min_file_size")
    p.add_argument("--max-file-size", dest="max_file_size")
    p.add_argument("--dedup", action="store_true", default=None)
    # download
    p.add_argument("--destdir")
    p.add_argument("--layout", choices=["collection", "item", "flat"])
    p.add_argument("--flat", action="store_true", default=None)
    p.add_argument("--workers", type=int)
    p.add_argument("--retries", type=int)
    p.add_argument("--resume", choices=["checksum", "fast-skip", "force"])
    p.add_argument("--force", action="store_true", default=None)
    p.add_argument("--ignore-errors", dest="ignore_errors", action="store_true", default=None)
    p.add_argument(
        "--no-ignore-errors", dest="ignore_errors", action="store_false", default=None
    )
    p.add_argument("--size-budget", dest="size_budget_gb", type=float)
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    p.add_argument("--manifest")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="archivedigger")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Cerca e scarica secondo il job/flag")
    run_p.add_argument("job", nargs="?", help="File YAML del job (opzionale)")
    _add_common_flags(run_p)

    search_p = sub.add_parser("search", help="Solo ricerca, stampa gli identifier")
    search_p.add_argument("job", nargs="?")
    _add_common_flags(search_p)

    est_p = sub.add_parser("estimate", help="Dry-run: stima item/file/GB")
    est_p.add_argument("job", nargs="?")
    _add_common_flags(est_p)

    exp_p = sub.add_parser("export-manifest", help="Esporta un manifest JSONL in CSV")
    exp_p.add_argument("manifest_path")
    exp_p.add_argument("-o", "--output", required=True)

    sub.add_parser("profiles", help="Elenca i profili preset")

    return parser.parse_args(argv)


def args_to_overrides(args: argparse.Namespace) -> dict[str, Any]:
    """Costruisce il dizionario di override dai soli flag passati."""
    overrides: dict[str, dict[str, Any]] = {}

    def put(section: str, field: str, value: Any) -> None:
        overrides.setdefault(section, {})[field] = value

    data = vars(args)
    for attr, (section, field) in _SCALAR_MAP.items():
        value = data.get(attr)
        if value is not None:
            put(section, field, value)
    for attr, (section, field) in _LIST_MAP.items():
        value = data.get(attr)
        if value:
            put(section, field, value)

    if data.get("prefer"):
        put("files", "prefer", parse_prefer(data["prefer"]))
    if data.get("dedup"):
        put("filters", "dedup", True)
    if data.get("dry_run"):
        put("download", "dry_run", True)
    if data.get("ignore_errors") is not None:
        put("download", "ignore_errors", data["ignore_errors"])
    if data.get("force"):
        put("download", "resume", "force")
    if data.get("flat"):
        put("download", "layout", "flat")

    return overrides


def config_from_args(args: argparse.Namespace) -> Config:
    """Costruisce la Config finale: profilo < job YAML < flag CLI."""
    job = None
    job_path = getattr(args, "job", None)
    if job_path:
        job = yaml.safe_load(Path(job_path).read_text(encoding="utf-8")) or {}
    profile = getattr(args, "profile", None)
    if profile is None and isinstance(job, dict):
        profile = job.pop("profile", None)
    return Config.build(profile=profile, job=job, overrides=args_to_overrides(args))


def main(argv: list[str] | None = None, client: Client | None = None) -> int:
    args = parse_args(argv)

    if args.command == "profiles":
        for name in list_profiles():
            print(name)
        return 0

    if args.command == "export-manifest":
        from .manifest import export_csv

        n = export_csv(args.manifest_path, args.output)
        print(f"Esportate {n} righe in {args.output}")
        return 0

    from . import api

    config = config_from_args(args)

    if args.command == "search":
        for identifier in api.search(config, client=client):
            print(identifier)
        return 0

    if args.command == "estimate":
        config.download.dry_run = True

    report = api.dig(config, client=client)
    print(
        f"item: {report.items}  scaricati: {report.downloaded}  "
        f"saltati: {report.skipped}  errori: {report.errors}  "
        f"byte: {report.bytes_downloaded}"
    )
    return 0
