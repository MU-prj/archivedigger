"""Orchestratore del download in massa.

Collega i pezzi: costruisce la query, cerca gli item, per ciascuno seleziona i
file (strategy di formato + catena di filtri), calcola il percorso locale
(layout), decide se saltarli (resume policy), rispetta il budget di dimensione
e la modalita' dry-run, scarica con retry e registra tutto nel manifest.

`plan()` fa la parte di sola lettura (ricerca + selezione), `run()` esegue.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .client import Client
from .config import Config
from .filters import build_file_filter
from .formats import build_format_strategy
from .layout import build_layout
from .manifest import Manifest, ManifestRecord
from .models import IAFile, IAItem
from .resume import build_resume_policy


@dataclass
class PlannedFile:
    item: IAItem
    file: IAFile
    local_path: Path


@dataclass
class Estimate:
    items: int = 0
    files: int = 0
    bytes: int = 0

    @property
    def gigabytes(self) -> float:
        return self.bytes / 1024**3


@dataclass
class DownloadReport:
    items: int = 0
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    bytes_downloaded: int = 0
    records: list[ManifestRecord] = field(default_factory=list)


class Downloader:
    def __init__(self, client: Client, config: Config, manifest: Manifest | None = None):
        self.client = client
        self.config = config
        self.format_strategy = build_format_strategy(config.files)
        self.layout = build_layout(config.download)
        self.resume = build_resume_policy(config.download)
        seen = manifest.seen_md5() if manifest else None
        self.file_filter = build_file_filter(config.filters, seen)
        self.manifest = manifest
        self._lock = threading.Lock()

    def plan(self) -> list[PlannedFile]:
        """Ricerca + selezione file, senza scaricare (usato anche dal dry-run)."""
        from .query import build_query

        query = build_query(self.config.search)
        destdir = Path(self.config.download.destdir)
        planned: list[PlannedFile] = []
        for identifier in self.client.search(
            query,
            sort=self.config.search.sort,
            max_items=self.config.search.max_items,
        ):
            item = self.client.get_item(identifier)
            selected = self.format_strategy.select(item.files)
            selected = self.file_filter.apply(selected)
            for f in selected:
                planned.append(PlannedFile(item, f, self.layout.path_for(destdir, item, f)))
        return planned

    def estimate(self) -> Estimate:
        """Stima (sola lettura) di item/file/byte che verrebbero scaricati.

        Applica il budget come il download reale, cosi' la stima combacia.
        """
        planned = self._apply_budget(self.plan())
        return Estimate(
            items=len({p.item.identifier for p in planned}),
            files=len(planned),
            bytes=sum(p.file.size or 0 for p in planned),
        )

    def run(self) -> DownloadReport:
        report = DownloadReport()
        planned = self._apply_budget(self.plan())
        report.items = len({p.item.identifier for p in planned})

        workers = max(1, self.config.download.workers)
        if workers == 1 or self.config.download.dry_run:
            for p in planned:
                self._process(p, report)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(lambda p: self._process(p, report), planned))
        return report

    def _apply_budget(self, planned: list[PlannedFile]) -> list[PlannedFile]:
        """Taglia il piano al budget di dimensione (deterministico, pre-download)."""
        budget = self._budget_bytes()
        if budget is None:
            return planned
        kept: list[PlannedFile] = []
        total = 0
        for p in planned:
            kept.append(p)
            total += p.file.size or 0
            if total >= budget:
                break
        return kept

    def _process(self, planned: PlannedFile, report: DownloadReport) -> None:
        item, file, path = planned.item, planned.file, planned.local_path

        if self.config.download.dry_run:
            self._record(report, item, file, path, "dry-run")
            return

        if self.resume.should_skip(path, file):
            with self._lock:
                report.skipped += 1
            self._record(report, item, file, path, "skipped")
            return

        try:
            self._download_with_retry(item, file, path)
        except Exception as exc:  # noqa: BLE001 - l'errore va nel manifest, non ferma il batch
            with self._lock:
                report.errors += 1
            self._record(report, item, file, path, "error", error=str(exc))
            if not self.config.download.ignore_errors:
                raise
            return

        with self._lock:
            report.downloaded += 1
            report.bytes_downloaded += file.size or 0
        self._record(report, item, file, path, "downloaded")

    def _download_with_retry(self, item: IAItem, file: IAFile, path: Path) -> None:
        attempts = max(1, self.config.download.retries)
        for attempt in range(attempts):
            try:
                self.client.download_file(item, file, path)
                return
            except Exception:
                if attempt + 1 >= attempts:
                    raise
                time.sleep(min(2**attempt, 30))

    def _record(self, report, item, file, path, status, error=None) -> None:
        record = ManifestRecord(
            identifier=item.identifier,
            file=file.name,
            format=file.format,
            size=file.size,
            md5=file.md5,
            source=file.source,
            collection=item.primary_collection,
            status=status,
            path=str(path),
            error=error,
        )
        with self._lock:
            report.records.append(record)
            if self.manifest is not None:
                self.manifest.append(record)

    def _budget_bytes(self) -> int | None:
        gb = self.config.download.size_budget_gb
        return int(gb * 1024**3) if gb else None
