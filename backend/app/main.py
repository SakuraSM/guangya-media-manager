import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cloud, dashboard, jobs, session, settings
from app.bootstrap import build_provider
from app.config import get_settings, validate_runtime_security
from app.database import SessionFactory, engine
from app.models import Base
from app.security import TokenCipher
from app.services.container import AppServices
from app.services.demo_seed import seed_demo_data
from app.services.login_manager import LoginManager
from app.services.metadata import AiRecognitionService, TmdbService
from app.services.organizer import OrganizerService
from app.services.queue import JobQueue
from app.services.runtime_settings import (
    apply_runtime_settings,
    load_runtime_settings,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    app_settings = get_settings()
    validate_runtime_security(app_settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    if app_settings.demo_mode:
        async with SessionFactory() as database_session:
            await seed_demo_data(database_session)

    provider = build_provider()
    tmdb_service = TmdbService(app_settings)
    ai_service = AiRecognitionService(app_settings)
    organizer = OrganizerService(
        session_factory=SessionFactory,
        provider=provider,
        tmdb_service=tmdb_service,
        ai_service=ai_service,
    )
    token_cipher = TokenCipher(app_settings)
    login_manager = LoginManager(provider, token_cipher)
    async with SessionFactory() as database_session:
        await login_manager.restore_session(database_session)
        runtime_settings = await load_runtime_settings(database_session, token_cipher, app_settings)
        apply_runtime_settings(runtime_settings, tmdb_service, ai_service)
    application.state.services = AppServices(
        provider=provider,
        login_manager=login_manager,
        organizer=organizer,
        queue=JobQueue(app_settings, organizer.run_action),
        token_cipher=token_cipher,
        tmdb_service=tmdb_service,
        ai_service=ai_service,
    )
    logger.info("Application services initialized")
    yield
    await engine.dispose()


app_settings = get_settings()
app = FastAPI(
    title="光鸭媒体管家 API",
    version="0.1.2",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(session.router, prefix="/api")
app.include_router(cloud.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.get("/healthz", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
