from app.config import get_settings
from app.database import SessionFactory
from app.providers.base import CloudProvider
from app.providers.demo import DemoGuangyaProvider
from app.providers.guangya import GuangyaProvider
from app.security import TokenCipher
from app.services.metadata import AiRecognitionService, TmdbService
from app.services.organizer import OrganizerService
from app.services.runtime_settings import apply_runtime_settings, load_runtime_settings


def build_provider() -> CloudProvider:
    settings = get_settings()
    if settings.demo_mode:
        return DemoGuangyaProvider()
    return GuangyaProvider()


async def build_organizer_service(
    provider: CloudProvider | None = None,
) -> OrganizerService:
    settings = get_settings()
    active_provider = provider or build_provider()
    tmdb_service = TmdbService(settings)
    ai_service = AiRecognitionService(settings)
    async with SessionFactory() as session:
        runtime_settings = await load_runtime_settings(session, TokenCipher(settings), settings)
        apply_runtime_settings(runtime_settings, tmdb_service, ai_service)
    return OrganizerService(
        session_factory=SessionFactory,
        provider=active_provider,
        tmdb_service=tmdb_service,
        ai_service=ai_service,
    )
