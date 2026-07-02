"""ResumePolicy: come trattare i file gia' presenti su disco (D11).

- ChecksumResume: salta se il file esiste e il suo MD5 coincide con quello
  atteso (ripresa idempotente, sopravvive ai file troncati da un crash).
- FastSkipResume: salta se il file esiste, senza verificare il contenuto.
- ForceRedownload: non salta mai, riscarica tutto.

Ogni policy espone should_skip(local_path, file) -> bool.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from .config import DownloadConfig
from .models import IAFile

_CHUNK = 1 << 20


class ResumePolicy(Protocol):
    def should_skip(self, local_path: Path, file: IAFile) -> bool:
        ...


class ForceRedownload:
    def should_skip(self, local_path: Path, file: IAFile) -> bool:
        return False


class FastSkipResume:
    def should_skip(self, local_path: Path, file: IAFile) -> bool:
        return local_path.exists()


class ChecksumResume:
    def should_skip(self, local_path: Path, file: IAFile) -> bool:
        if not local_path.exists():
            return False
        if not file.md5:
            return True  # niente MD5 atteso: ci si accontenta dell'esistenza
        return _md5(local_path) == file.md5


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


_POLICIES: dict[str, type[ResumePolicy]] = {
    "checksum": ChecksumResume,
    "fast-skip": FastSkipResume,
    "force": ForceRedownload,
}


def build_resume_policy(download: DownloadConfig) -> ResumePolicy:
    name = download.resume
    if name not in _POLICIES:
        available = ", ".join(sorted(_POLICIES))
        raise ValueError(f"Modalita' resume sconosciuta: {name!r}. Disponibili: {available}")
    return _POLICIES[name]()
