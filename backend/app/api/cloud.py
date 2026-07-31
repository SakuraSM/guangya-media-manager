import asyncio
import time
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

DIRECTORY_COUNT_CONCURRENCY = 4
DIRECTORY_COUNT_TTL_SECONDS = 60
_directory_count_cache: dict[str, tuple[float, int]] = {}


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
    directories = [node for node in nodes if node.is_directory]
    semaphore = asyncio.Semaphore(DIRECTORY_COUNT_CONCURRENCY)

    async def load_item_count(directory_id: str, directory_path: str) -> int | None:
        cached = _directory_count_cache.get(directory_id)
        now = time.monotonic()
        if cached is not None and now - cached[0] < DIRECTORY_COUNT_TTL_SECONDS:
            return cached[1]
        async with semaphore:
            try:
                children = await services.provider.list_directory(
                    directory_id,
                    directory_path,
                )
            except RuntimeError:
                return None
        item_count = len(children)
        _directory_count_cache[directory_id] = (now, item_count)
        return item_count

    item_counts = await asyncio.gather(
        *(load_item_count(node.id, node.path) for node in directories)
    )
    return [
        CloudDirectory(
            id=node.id,
            parent_id=node.parent_id,
            name=node.name,
            path=node.path,
            item_count=item_count,
        )
        for node, item_count in zip(directories, item_counts, strict=True)
    ]
