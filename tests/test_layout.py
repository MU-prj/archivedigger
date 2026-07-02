"""Test dei DiskLayout: dove finiscono i file scaricati su disco."""

from pathlib import Path

from archivedigger.config import DownloadConfig
from archivedigger.layout import (
    CollectionLayout,
    FlatLayout,
    ItemLayout,
    build_layout,
)
from archivedigger.models import IAFile, IAItem


def _item(identifier="show1", collection="jazz"):
    return IAItem(identifier=identifier, metadata={"collection": collection}, files=[])


def test_collection_layout_nests_collection_identifier_file():
    dest = Path("/downloads")
    p = CollectionLayout().path_for(dest, _item(), IAFile(name="a.flac"))
    assert p == dest / "jazz" / "show1" / "a.flac"


def test_collection_layout_without_collection_falls_back_to_identifier():
    dest = Path("/downloads")
    item = IAItem(identifier="show1", metadata={}, files=[])
    p = CollectionLayout().path_for(dest, item, IAFile(name="a.flac"))
    assert p == dest / "show1" / "a.flac"


def test_item_layout():
    dest = Path("/downloads")
    p = ItemLayout().path_for(dest, _item(), IAFile(name="a.flac"))
    assert p == dest / "show1" / "a.flac"


def test_flat_layout():
    dest = Path("/downloads")
    p = FlatLayout().path_for(dest, _item(), IAFile(name="a.flac"))
    assert p == dest / "a.flac"


def test_build_layout_from_config():
    assert isinstance(build_layout(DownloadConfig(layout="item")), ItemLayout)
    assert isinstance(build_layout(DownloadConfig(layout="flat")), FlatLayout)
    assert isinstance(build_layout(DownloadConfig()), CollectionLayout)


def test_build_layout_unknown_raises():
    import pytest

    with pytest.raises(ValueError, match="Layout"):
        build_layout(DownloadConfig(layout="bogus"))


def test_illegal_characters_are_sanitized():
    dest = Path("/downloads")
    item = IAItem(identifier="id:weird", metadata={"collection": 'a"b'}, files=[])
    p = CollectionLayout().path_for(dest, item, IAFile(name="a.flac"))
    assert p == dest / "a_b" / "id_weird" / "a.flac"
