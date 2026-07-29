import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.config import get_settings
from app.schemas import SessionLoginRequest, SessionState
from app.security import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    is_valid_session,
    set_session_cookie,
)

router = APIRouter(prefix="/session", tags=["session"])


@router.get("", response_model=SessionState)
async def get_session_state(request: Request) -> SessionState:
    settings = get_settings()
    session_value = request.cookies.get(SESSION_COOKIE_NAME, "")
    return SessionState(is_authenticated=is_valid_session(session_value, settings))


@router.post("/login", response_model=SessionState)
async def login(request: SessionLoginRequest, response: Response) -> SessionState:
    settings = get_settings()
    if not secrets.compare_digest(request.password, settings.admin_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员密码错误",
        )
    set_session_cookie(response)
    return SessionState(is_authenticated=True)


@router.post("/logout", response_model=SessionState)
async def logout(response: Response) -> SessionState:
    clear_session_cookie(response)
    return SessionState(is_authenticated=False)
