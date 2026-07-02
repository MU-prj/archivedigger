"""Test della facciata pubblica: e' il contratto per i repo consumatori."""

from archivedigger import api
from archivedigger.config import Config
from archivedigger.models import IAFile, IAItem


class FakeClient:
    def __init__(self, items):
        self._items = {it.identifier: it for it in items}
        self.downloaded = []

    def search(self, query, sort="downloads desc", max_items=100):
        return iter(list(self._items)[: max_items or None])

    def get_item(self, identifier):
        return self._items[identifier]

    def download_file(self, item, file, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"x")
        self.downloaded.append(file.name)


def _item(identifier="show1"):
    return IAItem(
        identifier=identifier,
        metadata={"collection": "jazz"},
        files=[IAFile(name="a.flac", format="Flac", size=1)],
    )


def test_dig_runs_download_and_returns_report(tmp_path):
    cfg = Config.build(job={"download": {"destdir": str(tmp_path)}})
    client = FakeClient([_item()])
    report = api.dig(cfg, client=client)
    assert report.downloaded == 1
    assert client.downloaded == ["a.flac"]


def test_estimate_reports_items_files_and_bytes(tmp_path):
    files = [
        IAFile(name="a.flac", format="Flac", size=600),
        IAFile(name="b.flac", format="Flac", size=400),
    ]
    cfg = Config.build(job={"download": {"destdir": str(tmp_path)}})
    client = FakeClient([_item("i1"), IAItem("i2", {"collection": "x"}, files)])
    est = api.estimate(cfg, client=client)
    assert est.items == 2
    assert est.files == 3
    assert est.bytes == 1 + 600 + 400  # _item() ha un file da 1 byte


def test_estimate_respects_budget(tmp_path):
    files = [IAFile(name=f"{i}.flac", format="Flac", size=1024**3) for i in range(5)]
    items = [IAItem(f"i{i}", {"collection": "x"}, [f]) for i, f in enumerate(files)]
    cfg = Config.build(job={"download": {"destdir": str(tmp_path), "size_budget_gb": 2}})
    est = api.estimate(cfg, client=FakeClient(items))
    assert est.files <= 3
    assert est.bytes >= 2 * 1024**3


def test_search_returns_identifiers():
    cfg = Config.build(job={"search": {"max_items": 10}})
    client = FakeClient([_item("a"), _item("b")])
    assert api.search(cfg, client=client) == ["a", "b"]


def test_dig_writes_manifest_when_configured(tmp_path):
    from archivedigger.manifest import Manifest

    manifest_path = tmp_path / "manifest.jsonl"
    cfg = Config.build(
        job={"download": {"destdir": str(tmp_path), "manifest": str(manifest_path)}}
    )
    api.dig(cfg, client=FakeClient([_item()]))
    assert len(Manifest(manifest_path).records()) == 1
