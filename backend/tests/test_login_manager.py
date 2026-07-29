from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base, CloudAccount
from app.providers.base import LoginChallenge, LoginTokens
from app.schemas import CloudLoginStatus
from app.security import TokenCipher
from app.services.login_manager import LoginManager


class RealAccountProviderStub:
    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token

    async def start_login(self) -> LoginChallenge:
        return LoginChallenge(
            device_code="device-code",
            verification_uri="https://example.test/device",
            expires_in_seconds=60,
            poll_interval_seconds=1,
        )

    async def poll_login(self, device_code: str) -> LoginTokens:
        return LoginTokens(access_token="access-token", refresh_token="refresh-token")

    async def get_storage_usage(self) -> tuple[int, int]:
        return (500_000, 123_456)


async def test_login_persists_real_storage_usage() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = RealAccountProviderStub()
    manager = LoginManager(provider, TokenCipher(get_settings()))  # type: ignore[arg-type]

    login = await manager.start_login()
    async with session_factory() as session:
        result: CloudLoginStatus = await manager.poll_login(login.login_id, session)
        account = await session.get(CloudAccount, result.account.id)  # type: ignore[union-attr]

    assert account is not None
    assert account.capacity_bytes == 500_000
    assert account.used_bytes == 123_456
    await engine.dispose()
