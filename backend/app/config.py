from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./media_manager.db"
    redis_url: str = "redis://localhost:6379/0"
    web_origin: str = "http://localhost:4173"
    admin_password: str = "change-me"
    session_secret: str = "development-session-secret-change-me"
    token_encryption_key: str = ""
    demo_mode: bool = True
    tmdb_api_token: str = ""
    tmdb_proxy_url: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4.1-mini"
    session_max_age_seconds: int = Field(default=86_400 * 14, ge=300)


@lru_cache
def get_settings() -> Settings:
    return Settings()
