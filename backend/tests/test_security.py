from app.config import Settings
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
