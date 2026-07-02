"""Test dei FileFilter client-side (durata, dimensione, dedup MD5)."""

from archivedigger.config import FiltersConfig
from archivedigger.filters import (
    DurationFilter,
    FileSizeFilter,
    Md5DedupFilter,
    build_file_filter,
)
from archivedigger.models import IAFile


def test_duration_filter_drops_too_short():
    files = [
        IAFile(name="jingle.mp3", length=3.0),
        IAFile(name="track.mp3", length=240.0),
    ]
    kept = DurationFilter(min_duration=30).apply(files)
    assert [f.name for f in kept] == ["track.mp3"]


def test_duration_filter_max_and_clock_format():
    files = [IAFile(name="long.mp3", length=7200.0), IAFile(name="ok.mp3", length=180.0)]
    kept = DurationFilter(max_duration="1:00:00").apply(files)
    assert [f.name for f in kept] == ["ok.mp3"]


def test_duration_filter_keeps_files_without_length():
    files = [IAFile(name="unknown.mp3", length=None)]
    assert DurationFilter(min_duration=30).apply(files) == files


def test_file_size_filter_bounds():
    files = [
        IAFile(name="tiny", size=100),
        IAFile(name="ok", size=5_000_000),
        IAFile(name="huge", size=500_000_000),
    ]
    kept = FileSizeFilter(min_size="500K", max_size="100M").apply(files)
    assert [f.name for f in kept] == ["ok"]


def test_md5_dedup_within_run():
    files = [
        IAFile(name="a", md5="x"),
        IAFile(name="b", md5="y"),
        IAFile(name="c", md5="x"),  # duplicato di a
    ]
    kept = Md5DedupFilter().apply(files)
    assert [f.name for f in kept] == ["a", "b"]


def test_md5_dedup_seeded_from_previous_run():
    files = [IAFile(name="a", md5="x"), IAFile(name="b", md5="y")]
    kept = Md5DedupFilter(seen={"x"}).apply(files)
    assert [f.name for f in kept] == ["b"]


def test_build_file_filter_composes_only_configured():
    files = [
        IAFile(name="short-dup", length=2.0, size=10, md5="x"),
        IAFile(name="good", length=200.0, size=5_000_000, md5="y"),
        IAFile(name="dup", length=200.0, size=5_000_000, md5="y"),
    ]
    chain = build_file_filter(
        FiltersConfig(min_duration=30, min_file_size="500K", dedup=True)
    )
    kept = chain.apply(files)
    assert [f.name for f in kept] == ["good"]


def test_build_file_filter_empty_config_keeps_all():
    files = [IAFile(name="a", length=1.0, size=1)]
    assert build_file_filter(FiltersConfig()).apply(files) == files
