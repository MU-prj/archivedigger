"""Test di integrazione: toccano Internet Archive reale.

Esclusi di default (marker `integration`). Per lanciarli:  make test-integration
oppure  pytest -m integration. Richiedono connessione di rete.
"""

import pytest

from archivedigger.client import InternetArchiveClient
from archivedigger.config import Config
from archivedigger.query import build_query

pytestmark = pytest.mark.integration


def test_real_search_returns_some_identifiers():
    client = InternetArchiveClient()
    query = build_query(Config.build(profile="corpus").search)
    ids = list(client.search(query, sort="downloads desc", max_items=3))
    assert len(ids) == 3
    assert all(isinstance(i, str) and i for i in ids)


def test_real_get_item_has_files():
    client = InternetArchiveClient()
    query = build_query(Config.build().search)
    identifier = next(iter(client.search(query, max_items=1)))
    item = client.get_item(identifier)
    assert item.identifier == identifier
    assert isinstance(item.files, list)


def test_real_download_file_lands_at_local_path(tmp_path):
    import hashlib

    client = InternetArchiveClient()
    query = build_query(Config.build().search)
    small = None
    for identifier in client.search(query, sort="downloads desc", max_items=10):
        item = client.get_item(identifier)
        sized = [f for f in item.files if f.size and "/" not in f.name]
        if sized:
            small = min(sized, key=lambda f: f.size)
            break
    assert small is not None, "nessun item con file dimensionati trovato"
    local_path = tmp_path / small.name
    client.download_file(item, small, local_path)

    assert local_path.exists()
    if small.md5:
        got = hashlib.md5(local_path.read_bytes()).hexdigest()
        assert got == small.md5
