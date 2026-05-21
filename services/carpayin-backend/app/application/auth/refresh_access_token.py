from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RefreshAccessTokenCommand:
    refresh_token: str


@dataclass(frozen=True)
class RefreshAccessTokenResult:
    app_access_token: str
    app_refresh_token: str | None = None


class RefreshAccessTokenService:
    def __init__(
        self,
        app_refresh_token_repository,
        refresh_token_hasher,
        app_access_token_issuer,
        now_provider=None,
    ):
        self.app_refresh_token_repository = app_refresh_token_repository
        self.refresh_token_hasher = refresh_token_hasher
        self.app_access_token_issuer = app_access_token_issuer
        self.now_provider = now_provider or self._now

    def execute(
        self,
        command: RefreshAccessTokenCommand,
    ) -> RefreshAccessTokenResult:
        if not command.refresh_token:
            raise ValueError("refresh_token is required")

        token_hash = self.refresh_token_hasher.hash(command.refresh_token)
        token_record = self.app_refresh_token_repository.find_by_hash(token_hash)
        if not token_record:
            raise ValueError("refresh_token_not_found")

        status = token_record["status"]
        if status == "revoked":
            raise ValueError("refresh_token_revoked")

        if status == "expired":
            raise ValueError("refresh_token_expired")

        if self._is_expired(token_record["expires_at"]):
            self.app_refresh_token_repository.mark_expired(token_hash)
            raise ValueError("refresh_token_expired")

        access_token = self.app_access_token_issuer.issue(
            user_id=token_record["user_id"],
            car_id=token_record["car_id"],
        )

        return RefreshAccessTokenResult(app_access_token=access_token)

    def _is_expired(self, expires_at) -> bool:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        return expires_at <= self.now_provider()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
