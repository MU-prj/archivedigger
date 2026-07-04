"""Test dell'orchestratore di download, con un client finto in-memory."""

from pathlib import Path

from archivedigger.config import Config
from archivedigger.downloader import Downloader
from archivedigger.models import IAFile, IAItem


class FakeClient:
    """Client in-memory: item predefiniti, download_file scrive un file vero."""

    def __init__(self, items):
        self._items = {it.identifier: it for it in items}
        self.downloaded: list[str] = []

    def search(self, query, sort="downloads desc", max_items=100):
        ids = list(self._items)
        return iter(ids if not max_items else ids[:max_items])

    def get_item(self, identifier):
        return self._items[identifier]

    def download_file(self, item, file, local_path: Path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"audio-bytes")
        self.downloaded.append(file.name)


def _item(identifier="show1", collection="jazz", files=None):
    return IAItem(
        identifier=identifier,
        metadata={"collection": collection},
        files=files or [IAFile(name="a.flac", format="Flac", size=11)],
    )


def _config(tmp_path, **download):
    data = {"download": {"destdir": str(tmp_path), "manifest": None, **download}}
    return Config.build(job=data)


def test_downloads_single_file(tmp_path):
    client = FakeClient([_item()])
    report = Downloader(client, _config(tmp_path)).run()
    assert report.downloaded == 1
    assert client.downloaded == ["a.flac"]
    assert (tmp_path / "show1__a.flac").exists()  # flat e' il default


def test_second_run_skips_already_downloaded(tmp_path):
    cfg = _config(tmp_path, resume="fast-skip")
    Downloader(FakeClient([_item()]), cfg).run()

    client2 = FakeClient([_item()])
    report = Downloader(client2, cfg).run()
    assert report.skipped == 1
    assert report.downloaded == 0
    assert client2.downloaded == []


def test_dry_run_does_not_download(tmp_path):
    client = FakeClient([_item()])
    report = Downloader(client, _config(tmp_path, dry_run=True)).run()
    assert client.downloaded == []
    assert report.downloaded == 0
    assert report.records[0].status == "dry-run"
    assert not (tmp_path / "jazz" / "show1" / "a.flac").exists()


def test_format_preference_selects_one_file_per_item(tmp_path):
    files = [
        IAFile(name="a.flac", format="Flac", size=100),
        IAFile(name="a.mp3", format="VBR MP3", size=10),
    ]
    cfg = Config.build(
        job={
            "download": {"destdir": str(tmp_path)},
            "files": {"prefer": [["Flac", "AIFF", "WAVE"], ["VBR MP3"]]},
        }
    )
    client = FakeClient([_item(files=files)])
    Downloader(client, cfg).run()
    assert client.downloaded == ["a.flac"]


def test_duration_filter_excludes_before_download(tmp_path):
    files = [
        IAFile(name="jingle.flac", format="Flac", size=1, length=2.0),
        IAFile(name="track.flac", format="Flac", size=100, length=300.0),
    ]
    cfg = Config.build(
        job={"download": {"destdir": str(tmp_path)}, "filters": {"min_duration": 30}}
    )
    client = FakeClient([_item(files=files)])
    Downloader(client, cfg).run()
    assert client.downloaded == ["track.flac"]


class ExplodingClient(FakeClient):
    def download_file(self, item, file, local_path):
        raise OSError("network down")


def test_error_is_isolated_when_ignore_errors(tmp_path):
    client = ExplodingClient([_item()])
    report = Downloader(client, _config(tmp_path, ignore_errors=True, retries=0)).run()
    assert report.errors == 1
    assert report.downloaded == 0
    assert report.records[0].status == "error"
    assert "network down" in report.records[0].error


def test_error_propagates_when_not_ignoring(tmp_path):
    import pytest

    client = ExplodingClient([_item()])
    cfg = _config(tmp_path, ignore_errors=False, retries=0)
    with pytest.raises(OSError, match="network down"):
        Downloader(client, cfg).run()


class CountingExplodingClient(FakeClient):
    def __init__(self, items):
        super().__init__(items)
        self.attempts = 0

    def download_file(self, item, file, local_path):
        self.attempts += 1
        raise OSError("network down")


def test_retries_means_additional_attempts(tmp_path, monkeypatch):
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda s: None)
    client = CountingExplodingClient([_item()])
    Downloader(client, _config(tmp_path, ignore_errors=True, retries=2)).run()
    assert client.attempts == 3  # 1 tentativo + 2 retry


def test_retries_zero_means_single_attempt(tmp_path):
    client = CountingExplodingClient([_item()])
    Downloader(client, _config(tmp_path, ignore_errors=True, retries=0)).run()
    assert client.attempts == 1


class BrokenItemClient(FakeClient):
    """get_item fallisce per un identifier specifico (item oscurato, 503...)."""

    def __init__(self, items, broken: str):
        super().__init__(items)
        self._broken = broken
        self._items[broken] = None  # compare nella ricerca ma non e' leggibile

    def get_item(self, identifier):
        if identifier == self._broken:
            raise ConnectionError("metadata fetch failed")
        return super().get_item(identifier)


def test_broken_item_does_not_kill_batch_when_ignoring_errors(tmp_path):
    client = BrokenItemClient([_item("ok1"), _item("ok2")], broken="dark1")
    report = Downloader(client, _config(tmp_path, ignore_errors=True)).run()
    assert report.downloaded == 2
    assert report.errors == 1
    broken = [r for r in report.records if r.status == "error"]
    assert broken[0].identifier == "dark1"
    assert "metadata fetch failed" in broken[0].error


def test_broken_item_propagates_when_not_ignoring(tmp_path):
    import pytest

    client = BrokenItemClient([_item("ok1")], broken="dark1")
    cfg = _config(tmp_path, ignore_errors=False)
    with pytest.raises(ConnectionError):
        Downloader(client, cfg).run()


def test_plan_error_is_written_to_manifest(tmp_path):
    from archivedigger.manifest import Manifest

    manifest = Manifest(tmp_path / "manifest.jsonl")
    client = BrokenItemClient([_item("ok1")], broken="dark1")
    Downloader(client, _config(tmp_path, ignore_errors=True), manifest=manifest).run()
    records = Manifest(tmp_path / "manifest.jsonl").records()
    errors = [r for r in records if r.status == "error"]
    assert [r.identifier for r in errors] == ["dark1"]


def test_budget_not_reached_keeps_whole_plan(tmp_path):
    # budget impostato ma mai raggiunto: il loop completa senza tagliare
    files = [IAFile(name=f"{i}.flac", format="Flac", size=1) for i in range(3)]
    items = [_item(identifier=f"i{i}", files=[f]) for i, f in enumerate(files)]
    cfg = Config.build(job={"download": {"destdir": str(tmp_path), "size_budget_gb": 100}})
    report = Downloader(FakeClient(items), cfg).run()
    assert report.downloaded == 3


def test_dedup_keeps_files_without_md5(tmp_path):
    # un file senza md5 non puo' essere dedotto: passa sempre, non entra nel set
    files = [
        IAFile(name="a.flac", format="Flac", size=1, md5=None),
        IAFile(name="b.flac", format="Flac", size=1, md5=None),
    ]
    cfg = Config.build(
        job={"download": {"destdir": str(tmp_path), "layout": "item"}, "filters": {"dedup": True}}
    )
    client = FakeClient([_item(files=files)])
    Downloader(client, cfg).run()
    assert sorted(client.downloaded) == ["a.flac", "b.flac"]


def test_estimate_then_run_on_same_downloader_with_dedup(tmp_path):
    # Md5DedupFilter e' stateful: estimate() non deve avvelenare il run()
    files = [IAFile(name="a.flac", format="Flac", size=10, md5="m1")]
    cfg = Config.build(
        job={"download": {"destdir": str(tmp_path)}, "filters": {"dedup": True}}
    )
    d = Downloader(FakeClient([_item(files=files)]), cfg)
    est = d.estimate()
    assert est.files == 1
    report = d.run()
    assert report.downloaded == 1


def test_failing_should_skip_is_recorded_as_error(tmp_path):
    # il percorso atteso esiste ma e' una directory: l'hash MD5 fallirebbe;
    # l'errore va nel manifest senza uccidere il batch
    (tmp_path / "show1__a.flac").mkdir()
    files = [IAFile(name="a.flac", format="Flac", size=None, md5="deadbeef")]
    client = FakeClient([_item(files=files)])
    report = Downloader(client, _config(tmp_path, resume="checksum")).run()
    assert report.errors == 1
    assert report.records[0].status == "error"


def test_size_budget_stops_download(tmp_path):
    files = [
        IAFile(name=f"{i}.flac", format="Flac", size=1024**3) for i in range(5)
    ]
    items = [_item(identifier=f"i{i}", files=[f]) for i, f in enumerate(files)]
    cfg = Config.build(
        job={"download": {"destdir": str(tmp_path), "size_budget_gb": 2}}
    )
    client = FakeClient(items)
    report = Downloader(client, cfg).run()
    # budget 2 GB, file da 1 GB: si ferma dopo aver superato il budget
    assert report.downloaded <= 3
    assert report.bytes_downloaded >= 2 * 1024**3


def test_manifest_is_written(tmp_path):
    from archivedigger.manifest import Manifest

    manifest = Manifest(tmp_path / "manifest.jsonl")
    client = FakeClient([_item()])
    Downloader(client, _config(tmp_path), manifest=manifest).run()
    records = Manifest(tmp_path / "manifest.jsonl").records()
    assert len(records) == 1
    assert records[0].status == "downloaded"


def test_parallel_workers_download_all_files(tmp_path):
    files = [IAFile(name=f"{i}.flac", format="Flac", size=10) for i in range(20)]
    items = [_item(identifier=f"i{i}", files=[f]) for i, f in enumerate(files)]
    cfg = _config(tmp_path, workers=4)
    client = FakeClient(items)
    report = Downloader(client, cfg).run()
    assert report.downloaded == 20
    assert sorted(client.downloaded) == sorted(f"{i}.flac" for i in range(20))
