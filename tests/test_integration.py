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
