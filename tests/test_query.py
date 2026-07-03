"""Test del QueryBuilder: traduzione dei campi search in query Lucene."""

import pytest

from archivedigger.config import SearchConfig
from archivedigger.query import build_query


def test_default_search_emits_mediatype_clause():
    q = build_query(SearchConfig())
    assert q == "mediatype:(audio OR etree)"


def test_single_collection_clause():
    q = build_query(SearchConfig(collection=["field-recordings"]))
    assert "collection:field-recordings" in q


def test_multiple_collections_or_grouped():
    q = build_query(SearchConfig(collection=["a", "b"]))
    assert "collection:(a OR b)" in q


def test_clauses_joined_with_and():
    q = build_query(SearchConfig(collection=["a"]))
    assert q == "mediatype:(audio OR etree) AND collection:a"


def test_creator_with_space_is_quoted():
    q = build_query(SearchConfig(creator="John Coltrane"))
    assert 'creator:"John Coltrane"' in q


def test_subject_list_or_grouped_and_quoted():
    q = build_query(SearchConfig(subject=["free jazz", "ambient"]))
    assert 'subject:("free jazz" OR ambient)' in q


def test_language_and_title_and_description():
    q = build_query(
        SearchConfig(language="eng", title="Live at the Village", description="soundboard")
    )
    assert "language:eng" in q
    assert 'title:"Live at the Village"' in q
    assert "description:soundboard" in q


def test_date_closed_range():
    q = build_query(SearchConfig(date_from="1990-01-01", date_to="2000-12-31"))
    assert "date:[1990-01-01 TO 2000-12-31]" in q


def test_date_open_upper_bound():
    q = build_query(SearchConfig(date_from="1990-01-01"))
    assert "date:[1990-01-01 TO *]" in q


def test_year_range():
    q = build_query(SearchConfig(year_from=1970, year_to=1979))
    assert "year:[1970 TO 1979]" in q


def test_added_after_uses_addeddate():
    q = build_query(SearchConfig(added_after="2020-01-01"))
    assert "addeddate:[2020-01-01 TO *]" in q


def test_license_any_emits_no_clause():
    q = build_query(SearchConfig(license="any"))
    assert "licenseurl" not in q


def test_license_publicdomain():
    q = build_query(SearchConfig(license="publicdomain"))
    assert "licenseurl:(*publicdomain*)" in q


def test_license_cc_matches_all_creative_commons():
    # Gli slash NON escapati dentro un wildcard fanno tornare 0 righe
    # all'API scrape di IA: la clausola deve usare \/ (bug 2026-07-03).
    q = build_query(SearchConfig(license="cc"))
    assert r"licenseurl:(*creativecommons.org\/licenses\/*)" in q
    assert "licenseurl:(*creativecommons.org/licenses/*)" not in q


def test_license_cc_commercial_excludes_noncommercial():
    q = build_query(SearchConfig(license="cc-commercial"))
    assert r"*creativecommons.org\/licenses\/*" in q
    assert "NOT licenseurl:*nc*" in q


def test_license_url_exact_takes_over_preset():
    url = "http://creativecommons.org/licenses/by/4.0/"
    q = build_query(SearchConfig(license="cc", license_url=url))
    assert f'licenseurl:"{url}"' in q
    assert r"*creativecommons.org\/licenses\/*" not in q


def test_unknown_license_preset_raises():
    with pytest.raises(ValueError, match="license"):
        build_query(SearchConfig(license="bogus"))


def test_min_downloads_range():
    q = build_query(SearchConfig(min_downloads=50))
    assert "downloads:[50 TO *]" in q


def test_downloads_closed_range():
    q = build_query(SearchConfig(min_downloads=50, max_downloads=1000))
    assert "downloads:[50 TO 1000]" in q


def test_min_rating_range():
    q = build_query(SearchConfig(min_rating=4.0))
    assert "avg_rating:[4.0 TO *]" in q


def test_item_size_parses_human_units_to_bytes():
    q = build_query(SearchConfig(min_item_size="10M"))
    assert "item_size:[10485760 TO *]" in q


def test_raw_query_is_anded_in_parentheses():
    q = build_query(SearchConfig(query="format:Flac AND year:1971"))
    assert "(format:Flac AND year:1971)" in q
    assert q.startswith("mediatype:(audio OR etree)")


def test_empty_mediatype_emits_no_mediatype_clause():
    q = build_query(SearchConfig(mediatype=[], collection=["a"]))
    assert q == "collection:a"
