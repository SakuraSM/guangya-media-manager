import base64
import hashlib
import hmac
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, Request, Response, status

from app.config import Settings, get_settings

SESSION_COOKIE_NAME = "guangya_media_session"


class TokenCipher:
    def __init__(self, settings: Settings) -> None:
        key = settings.token_encryption_key.strip()
        if key:
            encoded_key = key.encode()
        else:
            digest = hashlib.sha256(settings.session_secret.encode()).digest()
            encoded_key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(encoded_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as error:
            raise ValueError("Stored cloud credential cannot be decrypted") from error


def create_session_value(settings: Settings) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    payload = f"{issued_at}.{nonce}"
    signature = hmac.new(
        settings.session_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def is_valid_session(session_value: str, settings: Settings) -> bool:
    parts = session_value.split(".")
    if len(parts) != 3:
        return False
    issued_at, nonce, received_signature = parts
    payload = f"{issued_at}.{nonce}"
    expected_signature = hmac.new(
        settings.session_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(received_signature, expected_signature):
        return False
    try:
        session_age = int(time.time()) - int(issued_at)
    except ValueError:
        return False
    return 0 <= session_age <= settings.session_max_age_seconds


def set_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_value(settings),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def require_admin_session(request: Request) -> None:
    settings = get_settings()
    session_value = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not is_valid_session(session_value, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
