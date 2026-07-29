import time
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AccountStatus
from app.models import AuditEvent, CloudAccount
from app.providers.base import CloudProvider, LoginChallenge
from app.providers.demo import DEMO_CAPACITY_BYTES, DEMO_USED_BYTES
from app.schemas import CloudLoginStart, CloudLoginStatus
from app.security import TokenCipher

LOGIN_STATUS_PENDING = "PENDING"
LOGIN_STATUS_CONNECTED = "CONNECTED"
LOGIN_STATUS_EXPIRED = "EXPIRED"


@dataclass(slots=True)
class PendingLogin:
    login_id: str
    challenge: LoginChallenge
    expires_at: float


class LoginManager:
    def __init__(self, provider: CloudProvider, token_cipher: TokenCipher) -> None:
        self._provider = provider
        self._token_cipher = token_cipher
        self._pending_logins: dict[str, PendingLogin] = {}

    async def restore_session(self, session: AsyncSession) -> None:
        account = await session.scalar(select(CloudAccount).limit(1))
        if account is None or not account.encrypted_refresh_token:
            return
        account.status = AccountStatus.REFRESHING
        await session.commit()
        try:
            refresh_token = self._token_cipher.decrypt(
                account.encrypted_refresh_token
            )
            tokens = await self._provider.refresh_tokens(refresh_token)
        except (RuntimeError, ValueError):
            account.status = AccountStatus.REAUTH_REQUIRED
            session.add(
                AuditEvent(
                    event_type="ACCOUNT_REAUTH_REQUIRED",
                    message="光鸭登录凭证已失效，请重新扫码授权",
                    severity="warning",
                )
            )
            await session.commit()
            return
        self._provider.set_tokens(tokens.access_token, tokens.refresh_token)
        account.encrypted_refresh_token = self._token_cipher.encrypt(
            tokens.refresh_token
        )
        account.status = AccountStatus.CONNECTED
        session.add(
            AuditEvent(
                event_type="ACCOUNT_REFRESHED",
                message="光鸭账号登录状态已自动续期",
            )
        )
        await session.commit()

    async def start_login(self) -> CloudLoginStart:
        challenge = await self._provider.start_login()
        login_id = str(uuid4())
        self._pending_logins[login_id] = PendingLogin(
            login_id=login_id,
            challenge=challenge,
            expires_at=time.monotonic() + challenge.expires_in_seconds,
        )
        return CloudLoginStart(
            login_id=login_id,
            verification_uri=challenge.verification_uri,
            expires_in_seconds=challenge.expires_in_seconds,
            poll_interval_seconds=challenge.poll_interval_seconds,
        )

    async def poll_login(
        self, login_id: str, session: AsyncSession
    ) -> CloudLoginStatus:
        pending_login = self._pending_logins.get(login_id)
        if pending_login is None:
            return CloudLoginStatus(
                login_id=login_id,
                status=LOGIN_STATUS_EXPIRED,
                error_message="登录会话不存在或已过期",
            )
        if time.monotonic() > pending_login.expires_at:
            del self._pending_logins[login_id]
            return CloudLoginStatus(login_id=login_id, status=LOGIN_STATUS_EXPIRED)

        tokens = await self._provider.poll_login(pending_login.challenge.device_code)
        if tokens is None:
            return CloudLoginStatus(login_id=login_id, status=LOGIN_STATUS_PENDING)

        self._provider.set_tokens(tokens.access_token, tokens.refresh_token)
        account = await session.scalar(select(CloudAccount).limit(1))
        if account is None:
            account = CloudAccount()
            session.add(account)
        account.status = AccountStatus.CONNECTED
        account.encrypted_refresh_token = self._token_cipher.encrypt(tokens.refresh_token)
        account.capacity_bytes = DEMO_CAPACITY_BYTES
        account.used_bytes = DEMO_USED_BYTES
        session.add(
            AuditEvent(event_type="ACCOUNT_CONNECTED", message="光鸭账号连接成功")
        )
        await session.commit()
        await session.refresh(account)
        del self._pending_logins[login_id]
        return CloudLoginStatus(
            login_id=login_id,
            status=LOGIN_STATUS_CONNECTED,
            account=account,
        )
