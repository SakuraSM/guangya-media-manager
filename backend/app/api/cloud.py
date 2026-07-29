from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, Services
from app.models import CloudAccount
from app.schemas import (
    CloudAccountView,
    CloudDirectory,
    CloudLoginStart,
    CloudLoginStatus,
)
from app.security import require_admin_session

router = APIRouter(
    prefix="/cloud",
    tags=["cloud"],
    dependencies=[Depends(require_admin_session)],
)


@router.get("/account", response_model=CloudAccountView | None)
async def get_cloud_account(session: DatabaseSession) -> CloudAccount | None:
    account = await session.scalar(select(CloudAccount).limit(1))
    return account


@router.post("/guangya/login/start", response_model=CloudLoginStart)
async def start_guangya_login(
    services: Services,
) -> CloudLoginStart:
    return await services.login_manager.start_login()


@router.get("/guangya/login/{login_id}", response_model=CloudLoginStatus)
async def poll_guangya_login(
    login_id: str,
    session: DatabaseSession,
    services: Services,
) -> CloudLoginStatus:
    try:
        return await services.login_manager.poll_login(login_id, session)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="光鸭登录接口暂时不可用",
        ) from error


@router.get("/directories", response_model=list[CloudDirectory])
async def list_cloud_directories(
    services: Services,
    parent_id: Annotated[str, Query()] = "",
    parent_path: Annotated[str, Query()] = "/光鸭云盘",
) -> list[CloudDirectory]:
    try:
        nodes = await services.provider.list_directory(parent_id, parent_path)
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="无法读取光鸭目录",
        ) from error
    return [
        CloudDirectory(
            id=node.id,
            parent_id=node.parent_id,
            name=node.name,
            path=node.path,
            item_count=0,
        )
        for node in nodes
        if node.is_directory
    ]
