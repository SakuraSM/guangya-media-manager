from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import AppSetting
from app.security import TokenCipher
from app.services.metadata import AiRecognitionService, TmdbService


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    tmdb_api_token: str
    ai_api_key: str
    ai_base_url: str
    ai_model: str


async def load_runtime_settings(
    session: AsyncSession,
    cipher: TokenCipher,
    defaults: Settings,
) -> RuntimeSettings:
    records = list((await session.scalars(select(AppSetting))).all())
    stored_values: dict[str, str] = {}
    for record in records:
        try:
            stored_values[record.key] = cipher.decrypt(record.encrypted_value)
        except ValueError:
            continue
    return RuntimeSettings(
        tmdb_api_token=stored_values.get(
            "tmdb_api_token", defaults.tmdb_api_token
        ),
        ai_api_key=stored_values.get("ai_api_key", defaults.ai_api_key),
        ai_base_url=stored_values.get("ai_base_url", defaults.ai_base_url),
        ai_model=stored_values.get("ai_model", defaults.ai_model),
    )


async def save_runtime_setting(
    session: AsyncSession,
    cipher: TokenCipher,
    key: str,
    value: str,
) -> None:
    record = await session.get(AppSetting, key)
    encrypted_value = cipher.encrypt(value)
    if record is None:
        session.add(AppSetting(key=key, encrypted_value=encrypted_value))
        return
    record.encrypted_value = encrypted_value


def apply_runtime_settings(
    values: RuntimeSettings,
    tmdb_service: TmdbService,
    ai_service: AiRecognitionService,
) -> None:
    tmdb_service.configure(values.tmdb_api_token)
    ai_service.configure(
        api_key=values.ai_api_key,
        base_url=values.ai_base_url,
        model=values.ai_model,
    )
