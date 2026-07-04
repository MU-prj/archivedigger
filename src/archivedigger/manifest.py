"""Manifest: registro append-safe di cio' che e' stato scaricato o saltato.

Formato JSONL (un record JSON per riga): robusto ad append concorrente e a
crash a meta' download, machine-readable per i repo consumatori, adatto a
corpora enormi (streaming, niente riscrittura dell'intero file). L'export CSV
serve per l'ispezione umana.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
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
        return cls(**{k: v for k, v in data.items() if k in _KNOWN_FIELDS})


_KNOWN_FIELDS = frozenset(f.name for f in fields(ManifestRecord))


class Manifest:
    """Accesso a un file manifest JSONL su disco."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, record: ManifestRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def iter_records(self) -> Iterator[ManifestRecord]:
        """Scorre i record in streaming, senza caricare tutto in memoria.

        Una riga malformata (tipicamente l'ultima, troncata da un crash a
        meta' append) viene saltata: il manifest promette di sopravvivere ai
        crash, non puo' essere lui stesso il motivo per cui il run successivo
        non parte piu'.
        """
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield ManifestRecord.from_dict(data)

    def records(self) -> list[ManifestRecord]:
        return list(self.iter_records())

    def seen_md5(self) -> set[str]:
        """MD5 gia' registrati come scaricati (per seminare il dedup)."""
        return {
            r.md5
            for r in self.iter_records()
            if r.md5 and r.status == "downloaded"
        }


def export_csv(jsonl_path: str | Path, csv_path: str | Path) -> int:
    """Esporta un manifest JSONL in CSV; ritorna il numero di righe scritte.

    Streaming riga-per-riga: un manifest da milioni di record non deve stare
    tutto in memoria per una trasformazione lineare.
    """
    columns = [f.name for f in fields(ManifestRecord)]
    out = Path(csv_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for r in Manifest(jsonl_path).iter_records():
            writer.writerow(asdict(r))
            written += 1
    return written
