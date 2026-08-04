from dataclasses import dataclass
from typing import Protocol

from app.domain import MediaType, MetadataSource
from app.services.media_parser import ParsedMediaName
from app.services.metadata import MetadataCandidate, SeasonMetadata, TmdbService
from app.services.metadata_identity import ExternalIdentity, ExternalIdProvider, MetadataHint


@dataclass(frozen=True, slots=True)
class MetadataProviderCapabilities:
    search: bool
    external_identity: bool
    episode_details: bool
    languages: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalMetadataRecord:
    title: str
    original_title: str
    year: int | None
    media_type: MediaType
    overview: str
    season_number: int | None
    episode_number: int | None


class MetadataProvider(Protocol):
    source: MetadataSource
    display_name: str
    capabilities: MetadataProviderCapabilities

    @property
    def enabled(self) -> bool: ...

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]: ...

    async def resolve_identity(
        self,
        identity: ExternalIdentity,
        media_type: MediaType,
    ) -> MetadataCandidate | None: ...

    async def get_tv_season(
        self,
        provider_id: str,
        season_number: int,
    ) -> SeasonMetadata | None: ...


class TmdbMetadataProvider:
    source = MetadataSource.TMDB
    display_name = "TMDB"
    capabilities = MetadataProviderCapabilities(
        search=True,
        external_identity=True,
        episode_details=True,
        languages=("zh-CN", "en-US", "ja-JP", "ko-KR"),
    )

    def __init__(self, service: TmdbService) -> None:
        self._service = service

    @property
    def enabled(self) -> bool:
        return self._service.is_enabled

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]:
        return await self._service.search(parsed)

    async def resolve_identity(
        self,
        identity: ExternalIdentity,
        media_type: MediaType,
    ) -> MetadataCandidate | None:
        media_types = (
            (MediaType.TV, MediaType.MOVIE)
            if media_type == MediaType.UNKNOWN
            else (media_type,)
        )
        for resolved_type in media_types:
            candidate = (
                await self._service.get_candidate(
                    tmdb_id=int(identity.provider_id),
                    media_type=resolved_type,
                )
                if identity.provider == ExternalIdProvider.TMDB
                else await self._service.find_imdb_candidate(
                    imdb_id=identity.provider_id,
                    media_type=resolved_type,
                )
            )
            if candidate is not None:
                return candidate
        return None

    async def get_tv_season(
        self,
        provider_id: str,
        season_number: int,
    ) -> SeasonMetadata | None:
        return await self._service.get_tv_season(int(provider_id), season_number)


class LocalMetadataProvider:
    source = MetadataSource.LOCAL
    display_name = "本地 NFO"
    capabilities = MetadataProviderCapabilities(
        search=False,
        external_identity=False,
        episode_details=True,
        languages=(),
    )

    @property
    def enabled(self) -> bool:
        return True

    async def search(self, parsed: ParsedMediaName) -> list[MetadataCandidate]:
        return []

    async def resolve_identity(
        self,
        identity: ExternalIdentity,
        media_type: MediaType,
    ) -> MetadataCandidate | None:
        return None

    async def get_tv_season(
        self,
        provider_id: str,
        season_number: int,
    ) -> SeasonMetadata | None:
        return None

    def resolve_hint(
        self,
        hint: MetadataHint,
        fallback_media_type: MediaType,
    ) -> LocalMetadataRecord | None:
        title = " ".join(hint.title.split())
        if not title:
            return None
        return LocalMetadataRecord(
            title=title,
            original_title=" ".join(hint.original_title.split()),
            year=hint.year,
            media_type=(
                hint.media_type
                if hint.media_type != MediaType.UNKNOWN
                else fallback_media_type
            ),
            overview=hint.plot,
            season_number=hint.season_number,
            episode_number=hint.episode_number,
        )
