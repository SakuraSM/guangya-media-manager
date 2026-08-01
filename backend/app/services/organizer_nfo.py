from collections.abc import Iterable, Mapping
from html import escape
from pathlib import PurePosixPath

from app.domain import MediaType, MetadataSource
from app.models import MediaEntity, MediaEpisode, MediaMatch, MediaSeason

XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
MAX_NFO_ACTORS = 20


def render_media_nfo(entity: MediaEntity) -> str:
    root_tag = "tvshow" if entity.media_type == MediaType.TV else "movie"
    snapshot = entity.metadata_snapshot or {}
    common_lines = _common_media_lines(entity, snapshot)
    return _document(root_tag, common_lines)


def render_season_nfo(season: MediaSeason) -> str:
    snapshot = season.metadata_snapshot or {}
    lines = [
        _node("title", season.name),
        _node("seasonnumber", season.season_number),
        _node("premiered", _text(snapshot.get("air_date"))),
        _cdata_node("plot", season.overview),
    ]
    season_id = _integer(snapshot.get("id"))
    if season_id is not None:
        lines.append(_unique_id("tmdb", season_id, is_default=True))
    return _document("season", lines)


def render_episode_nfo(
    entity: MediaEntity,
    episode: MediaEpisode,
) -> str:
    snapshot = episode.metadata_snapshot or {}
    lines = [
        _node("title", episode.name),
        _node("showtitle", entity.title),
        _node("season", episode.media_season.season_number),
        _node("episode", episode.episode_number),
        _node("aired", episode.air_date.isoformat() if episode.air_date else ""),
        _node("rating", _number_text(snapshot.get("vote_average"))),
        _node("votes", _integer_text(snapshot.get("vote_count"))),
        _node("runtime", _integer_text(snapshot.get("runtime"))),
        _cdata_node("plot", episode.overview),
    ]
    if episode.tmdb_id is not None:
        lines.append(_unique_id("tmdb", episode.tmdb_id, is_default=True))
    return _document("episodedetails", lines)


def episode_nfo_filename(
    media_match: MediaMatch,
    episode: MediaEpisode,
    episode_count: int,
) -> str:
    stem = PurePosixPath(media_match.target_path).stem
    if episode_count == 1:
        return f"{stem}.nfo"
    season_number = episode.media_season.season_number
    return f"{stem}-S{season_number:02d}E{episode.episode_number:02d}.nfo"


def _common_media_lines(
    entity: MediaEntity,
    snapshot: Mapping[str, object],
) -> list[str]:
    lines = [
        _node("title", entity.title),
        _node("originaltitle", entity.original_title),
        _node("year", entity.year or ""),
        _node("premiered", _premiered(snapshot)),
        _node("rating", _number_text(snapshot.get("vote_average"))),
        _node("votes", _integer_text(snapshot.get("vote_count"))),
        _node("mpaa", _certification(snapshot, entity.media_type)),
        _node("runtime", _runtime(snapshot)),
        _node("status", _text(snapshot.get("status"))),
        _node("tagline", _text(snapshot.get("tagline"))),
        _cdata_node("plot", entity.overview),
        _cdata_node("outline", entity.overview),
    ]
    if entity.metadata_source != MetadataSource.LOCAL and entity.tmdb_id is not None:
        lines.append(_unique_id("tmdb", entity.tmdb_id, is_default=True))
    else:
        lines.append(_node("lockdata", "true"))
    lines.extend(_external_id_lines(snapshot))
    lines.extend(_named_collection_lines("genre", snapshot.get("genres")))
    lines.extend(_named_collection_lines("studio", snapshot.get("production_companies")))
    lines.extend(_country_lines(snapshot))
    lines.extend(_credit_lines(snapshot))
    return lines


def _external_id_lines(snapshot: Mapping[str, object]) -> list[str]:
    external_ids = _mapping(snapshot.get("external_ids"))
    identifiers = (
        ("imdb", _text(external_ids.get("imdb_id"))),
        ("tvdb", _integer_text(external_ids.get("tvdb_id"))),
    )
    return [
        _unique_id(provider, identifier, is_default=False)
        for provider, identifier in identifiers
        if identifier
    ]


def _credit_lines(snapshot: Mapping[str, object]) -> list[str]:
    credits = _mapping(snapshot.get("credits"))
    crew = _mapping_items(credits.get("crew"))
    cast = _mapping_items(credits.get("cast"))
    lines = [
        _node("director", _text(member.get("name")))
        for member in crew
        if _text(member.get("job")) == "Director" and _text(member.get("name"))
    ]
    lines.extend(
        _node("credits", _text(member.get("name")))
        for member in crew
        if _text(member.get("department")) == "Writing" and _text(member.get("name"))
    )
    lines.extend(_actor_node(member) for member in cast[:MAX_NFO_ACTORS])
    return lines


def _actor_node(actor: Mapping[str, object]) -> str:
    actor_lines = [
        _node("name", _text(actor.get("name"))),
        _node("role", _text(actor.get("character"))),
        _node("order", _integer_text(actor.get("order"))),
    ]
    return _nested_node("actor", actor_lines)


def _country_lines(snapshot: Mapping[str, object]) -> list[str]:
    production_countries = _mapping_items(snapshot.get("production_countries"))
    countries = [
        _text(country.get("name")) for country in production_countries if _text(country.get("name"))
    ]
    if not countries:
        origin_countries = snapshot.get("origin_country")
        if isinstance(origin_countries, list):
            countries = [country for country in origin_countries if isinstance(country, str)]
    return [_node("country", country) for country in countries]


def _named_collection_lines(tag: str, value: object) -> list[str]:
    return [_node(tag, name) for item in _mapping_items(value) if (name := _text(item.get("name")))]


def _premiered(snapshot: Mapping[str, object]) -> str:
    return _text(snapshot.get("release_date") or snapshot.get("first_air_date"))


def _runtime(snapshot: Mapping[str, object]) -> str:
    runtime = _integer(snapshot.get("runtime"))
    if runtime is not None:
        return str(runtime)
    episode_runtimes = snapshot.get("episode_run_time")
    if isinstance(episode_runtimes, list):
        for item in episode_runtimes:
            if isinstance(item, int):
                return str(item)
    return ""


def _certification(
    snapshot: Mapping[str, object],
    media_type: MediaType,
) -> str:
    response_key = "content_ratings" if media_type == MediaType.TV else "release_dates"
    payload = _mapping(snapshot.get(response_key))
    country_results = _mapping_items(payload.get("results"))
    preferred_results = sorted(
        country_results,
        key=lambda item: _country_rank(_text(item.get("iso_3166_1"))),
    )
    for result in preferred_results:
        if media_type == MediaType.TV:
            rating = _text(result.get("rating"))
            if rating:
                return rating
            continue
        for release in _mapping_items(result.get("release_dates")):
            certification = _text(release.get("certification"))
            if certification:
                return certification
    return ""


def _country_rank(country_code: str) -> int:
    if country_code == "CN":
        return 0
    if country_code == "US":
        return 1
    return 2


def _document(root_tag: str, lines: Iterable[str]) -> str:
    body = "\n".join(f"  {line}" for line in lines if line)
    return f"{XML_HEADER}\n<{root_tag}>\n{body}\n</{root_tag}>\n"


def _nested_node(tag: str, lines: Iterable[str]) -> str:
    body = "\n".join(f"    {line}" for line in lines if line)
    return f"<{tag}>\n{body}\n  </{tag}>"


def _node(tag: str, value: object) -> str:
    normalized = "" if value is None else str(value)
    return f"<{tag}>{escape(normalized)}</{tag}>"


def _cdata_node(tag: str, value: str | None) -> str:
    safe_value = (value or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<{tag}><![CDATA[{safe_value}]]></{tag}>"


def _unique_id(provider: str, value: object, *, is_default: bool) -> str:
    default_value = "true" if is_default else "false"
    return f'<uniqueid type="{provider}" default="{default_value}">{escape(str(value))}</uniqueid>'


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _mapping_items(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [_mapping(item) for item in value if isinstance(item, Mapping)]


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _integer_text(value: object) -> str:
    number = _integer(value)
    return str(number) if number is not None else ""


def _number_text(value: object) -> str:
    return str(value) if isinstance(value, int | float) else ""
