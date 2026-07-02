"""Test del manifest JSONL (registro append-safe) e dell'export CSV."""

import csv

from archivedigger.manifest import Manifest, ManifestRecord, export_csv


def test_append_and_read_roundtrip(tmp_path):
    path = tmp_path / "manifest.jsonl"
    manifest = Manifest(path)
    manifest.append(
        ManifestRecord(
            identifier="item1",
            file="a.flac",
            format="Flac",
            size=1000,
            md5="abc",
            status="downloaded",
        )
    )
    records = Manifest(path).records()
    assert len(records) == 1
    assert records[0].identifier == "item1"
    assert records[0].status == "downloaded"


def _rec(identifier, file, **kw):
    return ManifestRecord(identifier=identifier, file=file, **kw)


def test_append_is_additive(tmp_path):
    path = tmp_path / "m.jsonl"
    m = Manifest(path)
    m.append(_rec("i1", "a"))
    m.append(_rec("i2", "b"))
    assert [r.identifier for r in Manifest(path).records()] == ["i1", "i2"]


def test_seen_md5_only_downloaded(tmp_path):
    path = tmp_path / "m.jsonl"
    m = Manifest(path)
    m.append(_rec("i1", "a", md5="x", status="downloaded"))
    m.append(_rec("i2", "b", md5="y", status="error"))
    m.append(_rec("i3", "c", md5="z", status="skipped"))
    assert m.seen_md5() == {"x"}


def test_records_missing_file_is_empty(tmp_path):
    assert Manifest(tmp_path / "nope.jsonl").records() == []


def test_export_csv_writes_header_and_rows(tmp_path):
    jsonl = tmp_path / "m.jsonl"
    m = Manifest(jsonl)
    m.append(_rec("i1", "a.flac", format="Flac", size=10, status="downloaded"))
    m.append(_rec("i2", "b.mp3", format="VBR MP3", size=20, status="skipped"))

    csv_path = tmp_path / "out.csv"
    n = export_csv(jsonl, csv_path)
    assert n == 2

    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["identifier"] for r in rows] == ["i1", "i2"]
    assert rows[0]["format"] == "Flac"
