"""
차량 확정 / 앱 토큰 발급 유스케이스 단위 테스트
UC-AUTH-006: 앱 access token 재발급
"""

from datetime import datetime, timezone

import pytest

from app.application.auth.refresh_access_token import (
    RefreshAccessTokenCommand,
    RefreshAccessTokenService,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
VALID_REFRESH_TOKEN = "app-refresh-001"
VALID_REFRESH_TOKEN_HASH = "refresh-token-hash-001"
EXPIRED_REFRESH_TOKEN = "app-refresh-expired"
EXPIRED_REFRESH_TOKEN_HASH = "refresh-token-hash-expired"
REVOKED_REFRESH_TOKEN = "app-refresh-revoked"
REVOKED_REFRESH_TOKEN_HASH = "refresh-token-hash-revoked"
OTHER_REFRESH_TOKEN = "app-refresh-other"
VALID_USER_ID = "user-001"
VALID_CAR_ID = "car-001"
VALID_APP_ACCESS_TOKEN = "app-access-new-001"
ERROR_REFRESH_TOKEN_NOT_FOUND = "refresh_token_not_found"
ERROR_REFRESH_TOKEN_EXPIRED = "refresh_token_expired"
ERROR_REFRESH_TOKEN_REVOKED = "refresh_token_revoked"


class FakeAppRefreshTokenRepository:
    def __init__(self):
        self.tokens = {}
        self.expired_hashes = []

    def add_token(self, *, token_hash: str, status: str, expires_at: datetime):
        self.tokens[token_hash] = {
            "token_hash": token_hash,
            "status": status,
            "user_id": VALID_USER_ID,
            "car_id": VALID_CAR_ID,
            "expires_at": expires_at,
        }

    def find_by_hash(self, token_hash: str):
        return self.tokens.get(token_hash)

    def mark_expired(self, token_hash: str):
        self.expired_hashes.append(token_hash)
        self.tokens[token_hash]["status"] = "expired"


class FakeRefreshTokenHasher:
    def __init__(self):
        self.hashes = {
            VALID_REFRESH_TOKEN: VALID_REFRESH_TOKEN_HASH,
            EXPIRED_REFRESH_TOKEN: EXPIRED_REFRESH_TOKEN_HASH,
            REVOKED_REFRESH_TOKEN: REVOKED_REFRESH_TOKEN_HASH,
            OTHER_REFRESH_TOKEN: "refresh-token-hash-other",
        }

    def hash(self, refresh_token: str):
        return self.hashes[refresh_token]


class FakeAppAccessTokenIssuer:
    def __init__(self):
        self.issue_calls = []

    def issue(self, *, user_id: str, car_id: str):
        self.issue_calls.append(
            {
                "user_id": user_id,
                "car_id": car_id,
            }
        )
        return VALID_APP_ACCESS_TOKEN


@pytest.fixture
def fake_app_refresh_token_repository():
    return FakeAppRefreshTokenRepository()


@pytest.fixture
def fake_refresh_token_hasher():
    return FakeRefreshTokenHasher()


@pytest.fixture
def fake_app_access_token_issuer():
    return FakeAppAccessTokenIssuer()


@pytest.fixture
def refresh_access_token_service(
    fake_app_refresh_token_repository,
    fake_refresh_token_hasher,
    fake_app_access_token_issuer,
):
    return RefreshAccessTokenService(
        app_refresh_token_repository=fake_app_refresh_token_repository,
        refresh_token_hasher=fake_refresh_token_hasher,
        app_access_token_issuer=fake_app_access_token_issuer,
        now_provider=lambda: NOW,
    )


class TestRefreshAccessToken:
    """UC-AUTH-006 - POST /auth/refresh"""

    def test_active_refresh_token_returns_new_access_token(
        self,
        refresh_access_token_service,
        fake_app_refresh_token_repository,
        fake_app_access_token_issuer,
    ):
        """active refresh token이면 새 access token을 반환한다."""
        fake_app_refresh_token_repository.add_token(
            token_hash=VALID_REFRESH_TOKEN_HASH,
            status="active",
            expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        command = RefreshAccessTokenCommand(refresh_token=VALID_REFRESH_TOKEN)

        result = refresh_access_token_service.execute(command)

        assert result.app_access_token == VALID_APP_ACCESS_TOKEN
        assert result.app_refresh_token is None
        assert fake_app_access_token_issuer.issue_calls == [
            {
                "user_id": VALID_USER_ID,
                "car_id": VALID_CAR_ID,
            }
        ]

    def test_expired_refresh_token_marks_expired_and_raises_error(
        self,
        refresh_access_token_service,
        fake_app_refresh_token_repository,
        fake_app_access_token_issuer,
    ):
        """만료된 token이면 expired로 표시하고 실패한다."""
        fake_app_refresh_token_repository.add_token(
            token_hash=EXPIRED_REFRESH_TOKEN_HASH,
            status="active",
            expires_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
        command = RefreshAccessTokenCommand(refresh_token=EXPIRED_REFRESH_TOKEN)

        with pytest.raises(ValueError) as exc_info:
            refresh_access_token_service.execute(command)

        assert str(exc_info.value) == ERROR_REFRESH_TOKEN_EXPIRED
        assert fake_app_refresh_token_repository.expired_hashes == [
            EXPIRED_REFRESH_TOKEN_HASH
        ]
        assert fake_app_access_token_issuer.issue_calls == []

    def test_refresh_token_plaintext_is_not_stored(
        self,
        fake_app_refresh_token_repository,
    ):
        """원문 refresh token은 저장하지 않는다."""
        fake_app_refresh_token_repository.add_token(
            token_hash=VALID_REFRESH_TOKEN_HASH,
            status="active",
            expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )

        assert fake_app_refresh_token_repository.find_by_hash(VALID_REFRESH_TOKEN) is None
        assert (
            fake_app_refresh_token_repository.find_by_hash(VALID_REFRESH_TOKEN_HASH)
            is not None
        )

    def test_missing_refresh_token_raises_error(
        self,
        refresh_access_token_service,
    ):
        """token이 없으면 실패한다."""
        command = RefreshAccessTokenCommand(refresh_token=OTHER_REFRESH_TOKEN)

        with pytest.raises(ValueError) as exc_info:
            refresh_access_token_service.execute(command)

        assert str(exc_info.value) == ERROR_REFRESH_TOKEN_NOT_FOUND

    def test_revoked_refresh_token_raises_error(
        self,
        refresh_access_token_service,
        fake_app_refresh_token_repository,
    ):
        """revoked token이면 실패한다."""
        fake_app_refresh_token_repository.add_token(
            token_hash=REVOKED_REFRESH_TOKEN_HASH,
            status="revoked",
            expires_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        command = RefreshAccessTokenCommand(refresh_token=REVOKED_REFRESH_TOKEN)

        with pytest.raises(ValueError) as exc_info:
            refresh_access_token_service.execute(command)

        assert str(exc_info.value) == ERROR_REFRESH_TOKEN_REVOKED
