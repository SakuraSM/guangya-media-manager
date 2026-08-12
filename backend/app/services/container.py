from dataclasses import dataclass

from app.providers.base import CloudProvider
from app.security import TokenCipher
from app.services.login_manager import LoginManager
from app.services.metadata import AiRecognitionService, TmdbService
from app.services.organize_rules import OrganizeRuleService
from app.services.organizer import OrganizerService
from app.services.queue import JobQueue


@dataclass(frozen=True, slots=True)
class AppServices:
    provider: CloudProvider
    login_manager: LoginManager
    organizer: OrganizerService
    queue: JobQueue
    token_cipher: TokenCipher
    tmdb_service: TmdbService
    ai_service: AiRecognitionService
    rules: OrganizeRuleService
