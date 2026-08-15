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
    guangya_api_read_interval_seconds: float = Field(default=0.35, ge=0.05, le=10)
    guangya_api_write_interval_seconds: float = Field(default=1.2, ge=0.1, le=30)
    guangya_api_poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=30)
    guangya_api_jitter_seconds: float = Field(default=0.2, ge=0, le=5)
    guangya_api_max_retries: int = Field(default=3, ge=0, le=8)
    guangya_api_backoff_base_seconds: float = Field(default=2.0, ge=0.1, le=60)
    guangya_api_backoff_max_seconds: float = Field(default=30.0, ge=1, le=300)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_runtime_security(settings: Settings) -> None:
    if settings.demo_mode:
        return
    insecure_values = {
        "ADMIN_PASSWORD": {"", "change-me"},
        "SESSION_SECRET": {"", "development-session-secret-change-me"},
    }
    configured_values = {
        "ADMIN_PASSWORD": settings.admin_password,
        "SESSION_SECRET": settings.session_secret,
    }
    invalid_names = [
        name
        for name, value in configured_values.items()
        if value in insecure_values[name] or len(value) < 12
    ]
    if invalid_names:
        joined_names = ", ".join(invalid_names)
        raise RuntimeError(
            f"Refusing to start non-demo mode with insecure settings: {joined_names}"
        )
