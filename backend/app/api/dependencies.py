from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.container import AppServices


def get_services(request: Request) -> AppServices:
    services = request.app.state.services
    if not isinstance(services, AppServices):
        raise RuntimeError("Application services are not initialized")
    return services


DatabaseSession = Annotated[AsyncSession, Depends(get_session)]
Services = Annotated[AppServices, Depends(get_services)]
