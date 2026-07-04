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


# --- FileSelection: source + glob + formato composti dalla FilesConfig ---


def _sourced(*specs):
    """Helper: costruisce IAFile da tuple (name, format, source)."""
    return [IAFile(name=n, format=f, source=s) for n, f, s in specs]


def test_selection_source_original_excludes_derivatives():
    from archivedigger.formats import build_file_selection

    files = _sourced(("a.flac", "Flac", "original"), ("a.mp3", "VBR MP3", "derivative"))
    selection = build_file_selection(FilesConfig(source="original"))
    assert [f.name for f in selection.select(files)] == ["a.flac"]


def test_selection_source_any_keeps_all():
    from archivedigger.formats import build_file_selection

    files = _sourced(("a.flac", "Flac", "original"), ("a.mp3", "VBR MP3", "derivative"))
    selection = build_file_selection(FilesConfig(source="any"))
    assert selection.select(files) == files


def test_selection_unknown_source_is_never_excluded():
    # source assente nei metadati: la decisione non esclude (come i filtri range)
    from archivedigger.formats import build_file_selection

    files = _sourced(("a.flac", "Flac", None))
    selection = build_file_selection(FilesConfig(source="original"))
    assert [f.name for f in selection.select(files)] == ["a.flac"]


def test_selection_glob_include_and_exclude():
    from archivedigger.formats import build_file_selection

    files = _files(("live/a.flac", "Flac"), ("live/a.mp3", "VBR MP3"), ("cover.flac", "Flac"))
    selection = build_file_selection(FilesConfig(glob="live/*", exclude_glob="*.mp3"))
    assert [f.name for f in selection.select(files)] == ["live/a.flac"]


def test_selection_glob_is_case_insensitive():
    # le estensioni su IA arrivano in ogni combinazione di maiuscole
    from archivedigger.formats import build_file_selection

    files = _files(("Track01.FLAC", "Flac"), ("Bonus.MP3", "VBR MP3"))
    selection = build_file_selection(FilesConfig(glob="*.flac"))
    assert [f.name for f in selection.select(files)] == ["Track01.FLAC"]
    selection = build_file_selection(FilesConfig(exclude_glob="*.mp3"))
    assert [f.name for f in selection.select(files)] == ["Track01.FLAC"]


def test_selection_unknown_source_raises():
    # un typo ('originals') escluderebbe in silenzio quasi tutti i file
    import pytest

    from archivedigger.formats import build_file_selection

    with pytest.raises(ValueError, match="originals"):
        build_file_selection(FilesConfig(source="originals"))


def test_selection_source_applies_before_preference_chain():
    # Il flac e' derivative: con source=original la catena deve ripiegare sull'mp3
    from archivedigger.formats import build_file_selection

    files = _sourced(("a.flac", "Flac", "derivative"), ("a.mp3", "VBR MP3", "original"))
    selection = build_file_selection(
        FilesConfig(source="original", prefer=[["Flac"], ["VBR MP3"]])
    )
    assert [f.name for f in selection.select(files)] == ["a.mp3"]
