"""Test del client: wrapper su internetarchive con la libreria iniettata.

La libreria vera non viene mai toccata: si iniettano fake per search_items e
get_item, cosi' il contratto (dict di IA -> nostri modelli) e' verificabile
offline.
"""

from archivedigger.client import InternetArchiveClient
from archivedigger.models import IAItem


class FakeItem:
    """Mima internetarchive.item.Item: espone identifier, metadata, files."""

    def __init__(self, identifier, metadata, files):
        self.identifier = identifier
        self.metadata = metadata
        self.files = files


def test_search_yields_identifiers():
    def fake_search(query, fields=None, sorts=None, params=None):
        assert query == "mediatype:audio"
        return [{"identifier": "one"}, {"identifier": "two"}]

    client = InternetArchiveClient(search_fn=fake_search)
    ids = list(client.search("mediatype:audio", sort="downloads desc", max_items=10))
    assert ids == ["one", "two"]


def test_search_respects_max_items():
    def fake_search(query, fields=None, sorts=None, params=None):
        return [{"identifier": str(i)} for i in range(100)]

    client = InternetArchiveClient(search_fn=fake_search)
    ids = list(client.search("q", max_items=3))
    assert ids == ["0", "1", "2"]


def test_max_items_zero_means_unlimited():
    def fake_search(query, fields=None, sorts=None, params=None):
        return [{"identifier": str(i)} for i in range(5)]

    client = InternetArchiveClient(search_fn=fake_search)
    ids = list(client.search("q", max_items=0))
    assert ids == ["0", "1", "2", "3", "4"]


def test_search_error_row_raises_with_real_message():
    # su errore l'API scrape emette una riga {'error': ...} prima di fermarsi
    import pytest

    def fake_search(query, fields=None, sorts=None, params=None):
        return [{"error": "invalid query"}]

    client = InternetArchiveClient(search_fn=fake_search)
    with pytest.raises(ValueError, match="invalid query"):
        list(client.search("q"))


class _FakeIAModule:
    """Mima il modulo internetarchive per testare download_file offline."""

    def __init__(self, payload: dict[str, bytes]):
        self._payload = payload  # nome IA -> contenuto; vuoto = download a vuoto
        self.calls: list[dict] = []

    def download(self, identifier, files=None, destdir=None, **kwargs):
        from pathlib import Path

        self.calls.append({"identifier": identifier, "files": files, **kwargs})
        for name in files:
            if name in self._payload:
                target = Path(destdir) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self._payload[name])
        return []


def _download(monkeypatch, fake, item, file, local_path):
    import sys

    from archivedigger.models import IAFile, IAItem

    monkeypatch.setitem(sys.modules, "internetarchive", fake)
    client = InternetArchiveClient()
    client.download_file(
        IAItem(identifier=item, metadata={}, files=[]),
        IAFile(name=file),
        local_path,
    )


def test_download_file_lands_on_layout_path(tmp_path, monkeypatch):
    fake = _FakeIAModule({"disc1/a.flac": b"audio"})
    dest = tmp_path / "show1__disc1__a.flac"
    _download(monkeypatch, fake, "show1", "disc1/a.flac", dest)
    assert dest.read_bytes() == b"audio"
    # niente residui di staging in destdir
    assert [p.name for p in tmp_path.iterdir()] == ["show1__disc1__a.flac"]


def test_download_file_raises_when_nothing_lands(tmp_path, monkeypatch):
    import pytest

    fake = _FakeIAModule({})  # la libreria "salta" senza scaricare ne' alzare
    with pytest.raises(FileNotFoundError, match="show1"):
        _download(monkeypatch, fake, "show1", "a.flac", tmp_path / "show1__a.flac")


def test_get_item_translates_metadata_and_files():
    def fake_get_item(identifier):
        return FakeItem(
            identifier=identifier,
            metadata={"collection": ["jazz"], "title": "Show"},
            files=[
                {"name": "a.flac", "format": "Flac", "size": "1000",
                 "md5": "x", "length": "1:30", "source": "original"},
                {"name": "a.mp3", "format": "VBR MP3", "size": "200", "source": "derivative"},
            ],
        )

    client = InternetArchiveClient(get_item_fn=fake_get_item)
    item = client.get_item("show1")
    assert isinstance(item, IAItem)
    assert item.identifier == "show1"
    assert item.primary_collection == "jazz"
    assert item.files[0].size == 1000
    assert item.files[0].length == 90.0
    assert item.files[1].source == "derivative"
