import pytest

from app.config import Settings, validate_runtime_security
from app.security import TokenCipher, create_session_value, is_valid_session


def build_test_settings() -> Settings:
    return Settings(
        session_secret="test-session-secret-with-at-least-32-characters",
        token_encryption_key="",
    )


def test_encrypts_and_decrypts_refresh_token() -> None:
    cipher = TokenCipher(build_test_settings())

    encrypted_token = cipher.encrypt("refresh-secret")

    assert encrypted_token != "refresh-secret"
    assert cipher.decrypt(encrypted_token) == "refresh-secret"


def test_validates_signed_session() -> None:
    settings = build_test_settings()

    session_value = create_session_value(settings)

    assert is_valid_session(session_value, settings) is True
    assert is_valid_session(f"{session_value}tampered", settings) is False


def test_non_demo_mode_rejects_default_secrets() -> None:
    settings = Settings(
        demo_mode=False,
        admin_password="change-me",
        session_secret="development-session-secret-change-me",
    )

    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD, SESSION_SECRET"):
        validate_runtime_security(settings)


def test_non_demo_mode_accepts_unique_secrets() -> None:
    settings = Settings(
        demo_mode=False,
        admin_password="test-admin-password-with-strong-length",
        session_secret="test-session-secret-with-more-than-32-characters",
    )

    validate_runtime_security(settings)
