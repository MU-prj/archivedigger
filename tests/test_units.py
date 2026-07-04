"""Test degli helper di unita' (dimensioni e durate leggibili)."""

import pytest

from archivedigger.units import parse_duration, parse_size


def test_parse_size_plain_bytes():
    assert parse_size(1024) == 1024
    assert parse_size("2048") == 2048


def test_parse_size_binary_units():
    assert parse_size("1K") == 1024
    assert parse_size("10M") == 10 * 1024 * 1024
    assert parse_size("1G") == 1024**3


def test_parse_size_none_passthrough():
    assert parse_size(None) is None


def test_parse_size_rejects_garbage():
    with pytest.raises(ValueError, match="sconosciuta"):
        parse_size("abc")  # unita' sconosciuta


def test_parse_size_rejects_empty():
    with pytest.raises(ValueError, match="vuota"):
        parse_size("   ")


def test_parse_size_rejects_missing_number():
    # unita' valida ma nessun numero davanti ("M" -> magnitudine assente)
    with pytest.raises(ValueError, match="non valida"):
        parse_size("M")


def test_parse_duration_seconds():
    assert parse_duration(30) == 30.0
    assert parse_duration("45") == 45.0


def test_parse_duration_clock_format():
    assert parse_duration("1:30") == 90.0
    assert parse_duration("1:00:00") == 3600.0


def test_parse_duration_none_passthrough():
    assert parse_duration(None) is None


def test_parse_duration_rejects_empty_clock_part():
    with pytest.raises(ValueError, match="non valida"):
        parse_duration(":30")


def test_parse_duration_rejects_non_numeric():
    with pytest.raises(ValueError, match="non valida"):
        parse_duration("n/a")
