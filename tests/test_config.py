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


def test_list_profiles_returns_bundled_presets():
    assert list_profiles() == ["corpus", "dataset", "mirror"]


def test_build_without_profile_uses_defaults():
    cfg = Config.build()
    assert cfg.download.workers == 4
    assert cfg.search.mediatype == ["audio", "etree"]
    assert cfg.profile is None
