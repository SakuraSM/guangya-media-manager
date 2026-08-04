from fastapi import APIRouter, Depends

from app.api.dependencies import Services
from app.schemas import MetadataProviderView
from app.security import require_admin_session
from app.services.metadata_providers import LocalMetadataProvider, TmdbMetadataProvider

router = APIRouter(
    prefix="/metadata",
    tags=["metadata"],
    dependencies=[Depends(require_admin_session)],
)


@router.get("/providers", response_model=list[MetadataProviderView])
async def list_metadata_providers(services: Services) -> list[MetadataProviderView]:
    providers = (
        TmdbMetadataProvider(services.tmdb_service),
        LocalMetadataProvider(),
    )
    return [
        MetadataProviderView(
            provider=provider.source,
            display_name=provider.display_name,
            enabled=provider.enabled,
            capabilities={
                "search": provider.capabilities.search,
                "external_identity": provider.capabilities.external_identity,
                "episode_details": provider.capabilities.episode_details,
                "languages": list(provider.capabilities.languages),
            },
        )
        for provider in providers
    ]
