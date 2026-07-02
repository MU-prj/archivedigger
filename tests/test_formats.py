"""Test delle strategy di selezione formato (Exact, PreferenceChain)."""

from archivedigger.config import FilesConfig
from archivedigger.formats import (
    ExactFormatStrategy,
    PreferenceChainStrategy,
    build_format_strategy,
)
from archivedigger.models import IAFile


def _files(*specs):
    """Helper: costruisce IAFile da tuple (name, format)."""
    return [IAFile(name=n, format=f) for n, f in specs]


def test_exact_strategy_keeps_only_requested_format():
    files = _files(("a.flac", "Flac"), ("a.mp3", "VBR MP3"))
    selected = ExactFormatStrategy(formats=["Flac"]).select(files)
    assert [f.name for f in selected] == ["a.flac"]


def test_exact_strategy_empty_formats_keeps_all():
    files = _files(("a.flac", "Flac"), ("a.mp3", "VBR MP3"))
    assert ExactFormatStrategy(formats=[]).select(files) == files


PREFER = [["Flac", "AIFF", "WAVE"], ["VBR MP3"]]


def test_preference_picks_best_available_group():
    files = _files(("a.flac", "Flac"), ("a.mp3", "VBR MP3"))
    selected = PreferenceChainStrategy(PREFER).select(files)
    assert [f.name for f in selected] == ["a.flac"]


def test_preference_falls_back_to_next_group():
    files = _files(("a.mp3", "VBR MP3"), ("a.ogg", "Ogg Vorbis"))
    selected = PreferenceChainStrategy(PREFER).select(files)
    assert [f.name for f in selected] == ["a.mp3"]


def test_preference_group_is_ex_aequo():
    # Flac, AIFF, WAVE nello stesso gruppo: se presenti piu' d'uno, li prende tutti
    files = _files(("a.flac", "Flac"), ("a.aiff", "AIFF"), ("a.mp3", "VBR MP3"))
    selected = PreferenceChainStrategy(PREFER).select(files)
    assert {f.name for f in selected} == {"a.flac", "a.aiff"}


def test_preference_no_match_returns_empty():
    files = _files(("a.txt", "Text"))
    assert PreferenceChainStrategy(PREFER).select(files) == []


def test_factory_uses_preference_when_prefer_set():
    strategy = build_format_strategy(FilesConfig(prefer=PREFER))
    assert isinstance(strategy, PreferenceChainStrategy)


def test_factory_uses_exact_when_only_formats_set():
    strategy = build_format_strategy(FilesConfig(formats=["Flac"]))
    assert isinstance(strategy, ExactFormatStrategy)


def test_factory_default_keeps_all_files():
    files = _files(("a.flac", "Flac"), ("a.mp3", "VBR MP3"))
    strategy = build_format_strategy(FilesConfig())
    assert strategy.select(files) == files
