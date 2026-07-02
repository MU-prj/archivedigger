"""Test delle ResumePolicy: decidere se un file gia' presente va rifatto."""

import hashlib

from archivedigger.config import DownloadConfig
from archivedigger.models import IAFile
from archivedigger.resume import (
    ChecksumResume,
    FastSkipResume,
    ForceRedownload,
    build_resume_policy,
)


def _write(path, data: bytes = b"hello"):
    path.write_bytes(data)
    return hashlib.md5(data).hexdigest()


def test_fast_skip_skips_existing_file(tmp_path):
    p = tmp_path / "a.flac"
    _write(p)
    assert FastSkipResume().should_skip(p, IAFile(name="a.flac")) is True


def test_fast_skip_downloads_missing_file(tmp_path):
    p = tmp_path / "missing.flac"
    assert FastSkipResume().should_skip(p, IAFile(name="missing.flac")) is False


def test_checksum_skips_when_md5_matches(tmp_path):
    p = tmp_path / "a.flac"
    md5 = _write(p)
    assert ChecksumResume().should_skip(p, IAFile(name="a.flac", md5=md5)) is True


def test_checksum_redownloads_when_md5_differs(tmp_path):
    p = tmp_path / "a.flac"
    _write(p, b"corrupted")
    assert ChecksumResume().should_skip(p, IAFile(name="a.flac", md5="deadbeef")) is False


def test_checksum_without_expected_md5_uses_existence(tmp_path):
    p = tmp_path / "a.flac"
    _write(p)
    assert ChecksumResume().should_skip(p, IAFile(name="a.flac", md5=None)) is True


def test_force_never_skips(tmp_path):
    p = tmp_path / "a.flac"
    _write(p)
    assert ForceRedownload().should_skip(p, IAFile(name="a.flac")) is False


def test_build_resume_policy_from_config():
    assert isinstance(build_resume_policy(DownloadConfig(resume="checksum")), ChecksumResume)
    assert isinstance(build_resume_policy(DownloadConfig(resume="fast-skip")), FastSkipResume)
    assert isinstance(build_resume_policy(DownloadConfig(resume="force")), ForceRedownload)


def test_build_resume_policy_unknown_raises():
    import pytest

    with pytest.raises(ValueError, match="resume"):
        build_resume_policy(DownloadConfig(resume="bogus"))
