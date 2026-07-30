from fastapi import APIRouter, Depends

from app.api.dependencies import DatabaseSession, Services
from app.config import get_settings
from app.models import AuditEvent
from app.schemas import SettingsView, UpdateSettingsRequest
from app.security import require_admin_session
from app.services.runtime_settings import (
    RuntimeSettings,
    apply_runtime_settings,
    load_runtime_settings,
    save_runtime_setting,
)

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_admin_session)],
)


@router.get("", response_model=SettingsView)
async def get_app_settings(
    session: DatabaseSession,
    services: Services,
) -> SettingsView:
    settings = get_settings()
    values = await load_runtime_settings(session, services.token_cipher, settings)
    return SettingsView(
        demo_mode=settings.demo_mode,
        tmdb_configured=bool(values.tmdb_api_token),
        ai_configured=bool(values.ai_api_key),
        ai_base_url=values.ai_base_url,
        ai_model=values.ai_model,
        auto_approve_threshold=0.9,
        review_threshold=0.65,
    )


@router.put("", response_model=SettingsView)
async def update_app_settings(
    request: UpdateSettingsRequest,
    session: DatabaseSession,
    services: Services,
) -> SettingsView:
    settings = get_settings()
    current = await load_runtime_settings(session, services.token_cipher, settings)
    requested_updates = {
        "tmdb_api_token": request.tmdb_api_token,
        "ai_base_url": request.ai_base_url,
        "ai_api_key": request.ai_api_key,
        "ai_model": request.ai_model,
    }
    for key, value in requested_updates.items():
        if value:
            await save_runtime_setting(session, services.token_cipher, key, value)

    updated = RuntimeSettings(
        tmdb_api_token=request.tmdb_api_token or current.tmdb_api_token,
        ai_api_key=request.ai_api_key or current.ai_api_key,
        ai_base_url=request.ai_base_url or current.ai_base_url,
        ai_model=request.ai_model or current.ai_model,
    )
    apply_runtime_settings(updated, services.tmdb_service, services.ai_service)
    session.add(
        AuditEvent(
            event_type="SETTINGS_UPDATED",
            message="元数据服务设置已更新",
        )
    )
    await session.commit()
    return SettingsView(
        demo_mode=settings.demo_mode,
        tmdb_configured=bool(updated.tmdb_api_token),
        ai_configured=bool(updated.ai_api_key),
        ai_base_url=updated.ai_base_url,
        ai_model=updated.ai_model,
        auto_approve_threshold=0.9,
        review_threshold=0.65,
    )
