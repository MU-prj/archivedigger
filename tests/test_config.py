"""Test del modulo config: caricamento profili e merge di precedenza.

Precedenza attesa: default < profilo < job YAML < override CLI.
"""

import pytest

from archivedigger.config import Config, list_profiles


def test_build_from_profile_reads_profile_values():
    # corpus.yaml definisce download.workers: 4
    cfg = Config.build(profile="corpus")
    assert cfg.download.workers == 4


def test_job_overrides_profile():
    cfg = Config.build(profile="corpus", job={"download": {"workers": 8}})
    assert cfg.download.workers == 8


def test_cli_override_beats_job():
    cfg = Config.build(
        profile="corpus",
        job={"download": {"workers": 8}},
        overrides={"download": {"workers": 16}},
    )
    assert cfg.download.workers == 16


def test_partial_override_preserves_sibling_fields():
    # corpus.yaml fissa anche retries:3; sovrascrivere workers non deve azzerarlo
    cfg = Config.build(profile="corpus", job={"download": {"workers": 8}})
    assert cfg.download.workers == 8
    assert cfg.download.retries == 3


def test_none_values_do_not_clobber_lower_layer():
    # i template YAML dichiarano i campi come null: non devono azzerare il profilo
    cfg = Config.build(profile="corpus", job={"download": {"workers": None}})
    assert cfg.download.workers == 4


def test_unknown_profile_raises_with_available_list():
    with pytest.raises(ValueError, match="corpus"):
        Config.build(profile="nonesiste")


def test_unknown_field_in_section_raises():
    with pytest.raises(ValueError, match="workerz"):
        Config.build(job={"download": {"workerz": 8}})


def test_unknown_top_level_section_raises():
    # il typo "filter:" non deve far sparire silenziosamente tutti i filtri
    with pytest.raises(ValueError, match="filter"):
        Config.build(job={"filter": {"min_duration": 5}})


def test_scalar_string_coerced_to_list_field():
    # in YAML e' naturale scrivere collection: librivoxaudio (scalare)
    cfg = Config.build(job={"search": {"collection": "librivoxaudio"}})
    assert cfg.search.collection == ["librivoxaudio"]


def test_scalar_coercion_covers_all_string_list_fields():
    cfg = Config.build(
        job={
            "search": {"mediatype": "audio", "subject": "jazz"},
            "files": {"formats": "Flac"},
        }
    )
    assert cfg.search.mediatype == ["audio"]
    assert cfg.search.subject == ["jazz"]
    assert cfg.files.formats == ["Flac"]


def test_non_dict_section_raises_config_error():
    # 'files: [Flac]' deve dare l'errore di config, non un AttributeError
    with pytest.raises(ValueError, match="Flac"):
        Config.build(job={"files": ["Flac"]})


def test_flat_prefer_groups_are_nested():
    # prefer: [Flac, VBR MP3] scritto piatto = un gruppo per formato
    cfg = Config.build(job={"files": {"prefer": ["Flac", "VBR MP3"]}})
    assert cfg.files.prefer == [["Flac"], ["VBR MP3"]]


def test_formats_override_clears_inherited_prefer():
    # il profilo corpus imposta prefer; --formats a un livello sopra deve
    # vincere, non essere ignorato perche' prefer ha la precedenza
    cfg = Config.build(profile="corpus", overrides={"files": {"formats": ["VBR MP3"]}})
    assert cfg.files.formats == ["VBR MP3"]
    assert cfg.files.prefer == []


def test_prefer_override_clears_inherited_formats():
    cfg = Config.build(
        job={"files": {"formats": ["Flac"]}},
        overrides={"files": {"prefer": [["VBR MP3"]]}},
    )
    assert cfg.files.prefer == [["VBR MP3"]]
    assert cfg.files.formats == []


def test_list_profiles_returns_bundled_presets():
    assert list_profiles() == ["corpus", "dataset", "mirror"]


def test_build_without_profile_uses_defaults():
    cfg = Config.build()
    assert cfg.download.workers == 4
    assert cfg.search.mediatype == ["audio", "etree"]
    assert cfg.profile is None
