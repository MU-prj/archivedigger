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
        # una dimensione diversa da quella attesa e' gia' la prova che il file
        # e' incompleto (crash a meta' download): niente skip, e per i file
        # integri si evita di ri-leggere l'intero contenuto solo per l'hash
        if file.size is not None and local_path.stat().st_size != file.size:
            return False
        if not file.md5:
            return True  # niente MD5 atteso: esistenza + dimensione bastano
        return _md5(local_path) == file.md5


def _md5(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "md5").hexdigest()


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
