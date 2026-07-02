"""Manifest: registro append-safe di cio' che e' stato scaricato o saltato.

Formato JSONL (un record JSON per riga): robusto ad append concorrente e a
crash a meta' download, machine-readable per i repo consumatori, adatto a
corpora enormi (streaming, niente riscrittura dell'intero file). L'export CSV
serve per l'ispezione umana.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


@dataclass
class ManifestRecord:
    identifier: str
    file: str
    format: str | None = None
    size: int | None = None
    md5: str | None = None
    source: str | None = None
    collection: str | None = None
    status: str = "downloaded"  # downloaded | skipped | error | dry-run
    path: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestRecord:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class Manifest:
    """Accesso a un file manifest JSONL su disco."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, record: ManifestRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def records(self) -> list[ManifestRecord]:
        if not self.path.exists():
            return []
        out: list[ManifestRecord] = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(ManifestRecord.from_dict(json.loads(line)))
        return out

    def seen_md5(self) -> set[str]:
        """MD5 gia' registrati come scaricati (per seminare il dedup)."""
        return {
            r.md5
            for r in self.records()
            if r.md5 and r.status == "downloaded"
        }


def export_csv(jsonl_path: str | Path, csv_path: str | Path) -> int:
    """Esporta un manifest JSONL in CSV; ritorna il numero di righe scritte."""
    records = Manifest(jsonl_path).records()
    columns = [f.name for f in fields(ManifestRecord)]
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for r in records:
            writer.writerow(asdict(r))
    return len(records)
