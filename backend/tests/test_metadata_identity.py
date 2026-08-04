import pytest

from app.domain import MatchOrigin, MediaType
from app.services.metadata_identity import (
    ExternalIdProvider,
    MetadataHintError,
    choose_nfo_path,
    extract_path_hint,
    parse_nfo,
)
from app.services.metadata_providers import LocalMetadataProvider


def test_directory_tmdb_identity_takes_priority_over_filename() -> None:
    hint = extract_path_hint(
        "/剧集/三体 {tmdb-204541}/Season 01/E01 [tmdbid=999].mkv",
        filename="E01 [tmdbid=999].mkv",
    )

    assert hint is not None
    assert hint.origin == MatchOrigin.PATH_ID
    assert hint.identity is not None
    assert hint.identity.provider == ExternalIdProvider.TMDB
    assert hint.identity.provider_id == "204541"


def test_parse_common_tvshow_nfo_identity_and_local_fields() -> None:
    hint = parse_nfo(
        b"""<?xml version="1.0" encoding="UTF-8"?>
        <tvshow>
          <title>Example Show</title><originaltitle>Original</originaltitle>
          <year>2024</year><plot>Plot</plot>
          <uniqueid type="tmdb" default="true">12345</uniqueid>
        </tvshow>""",
        source_path="/shows/Example/tvshow.nfo",
    )

    assert hint.media_type == MediaType.TV
    assert hint.title == "Example Show"
    assert hint.year == 2024
    assert hint.identity is not None
    assert hint.identity.provider_id == "12345"


def test_parse_nfo_rejects_doctype_and_entities() -> None:
    with pytest.raises(MetadataHintError) as error:
        parse_nfo(b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><movie/>')

    assert error.value.reason_code == "NFO_UNSAFE_XML"


def test_nfo_association_precedence() -> None:
    paths = {
        "/shows/Example/Season 01/E01.nfo",
        "/shows/Example/Season 01/tvshow.nfo",
        "/shows/Example/tvshow.nfo",
    }

    assert (
        choose_nfo_path("/shows/Example/Season 01/E01.mkv", paths)
        == "/shows/Example/Season 01/E01.nfo"
    )


def test_local_provider_converts_title_only_nfo_to_local_record() -> None:
    hint = parse_nfo(b"<tvshow><title>Local Short Drama</title><year>2025</year></tvshow>")

    record = LocalMetadataProvider().resolve_hint(hint, MediaType.UNKNOWN)

    assert record is not None
    assert record.title == "Local Short Drama"
    assert record.media_type == MediaType.TV
    assert record.year == 2025
