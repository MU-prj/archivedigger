"""IAFile.from_dict deve reggere i metadati sporchi di Internet Archive.

Casi reali incontrati in produzione (2026-07-03): `size` che arriva come
lista, durate non parsabili. Un metadato illeggibile non deve far crollare
l'intero plan(): diventa None (metrica ignota, decide la catena di filtri).
"""

import pytest

from archivedigger.models import IAFile


def test_size_lista_prende_il_primo_valore():
    f = IAFile.from_dict({"name": "a.wav", "size": ["123", "456"]})
    assert f.size == 123


def test_size_non_numerica_diventa_none():
    f = IAFile.from_dict({"name": "a.wav", "size": "boh"})
    assert f.size is None


def test_length_lista_prende_il_primo_valore():
    f = IAFile.from_dict({"name": "a.wav", "length": ["12.5"]})
    assert f.length == pytest.approx(12.5)


def test_length_non_parsabile_diventa_none():
    f = IAFile.from_dict({"name": "a.wav", "length": "n/a"})
    assert f.length is None


def test_lista_vuota_diventa_none():
    f = IAFile.from_dict({"name": "a.wav", "size": [], "length": []})
    assert f.size is None
    assert f.length is None


def test_format_lista_prende_il_primo_valore():
    # tag ripetuto in files.xml: una lista qui sarebbe unhashable nelle strategy
    f = IAFile.from_dict({"name": "a.mp3", "format": ["VBR MP3", "MP3"]})
    assert f.format == "VBR MP3"


def test_name_e_md5_lista_prendono_il_primo_valore():
    f = IAFile.from_dict({"name": ["a.wav"], "md5": ["abc", "def"], "source": ["original"]})
    assert f.name == "a.wav"
    assert f.md5 == "abc"
    assert f.source == "original"


def test_name_mancante_diventa_stringa_vuota():
    f = IAFile.from_dict({})
    assert f.name == ""


def test_metadati_puliti_restano_intatti():
    f = IAFile.from_dict({"name": "a.wav", "size": "1000",
                          "length": "1:30", "format": "WAVE"})
    assert f.size == 1000
    assert f.length == pytest.approx(90.0)
