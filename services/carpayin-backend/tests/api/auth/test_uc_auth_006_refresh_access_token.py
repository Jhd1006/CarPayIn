"""앱 Access Token 재발급 API 테스트
UC-AUTH-006: POST /auth/refresh
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_refresh_token_service
from app.application.auth.refresh_access_token import RefreshAccessTokenResult

# 3. 테스트 상수
VALID_REFRESH_TOKEN = "valid-refresh-token"
NEW_ACCESS_TOKEN = "new-access-token"
# main.py의 exception_handler와 일치하는 메시지 사용
INVALID_TOKEN_MSG = "invalid_token" 

# 4. Stub 클래스
class StubRefreshAccessTokenService:
    def execute(self, token: str):
        return RefreshAccessTokenResult(app_access_token=NEW_ACCESS_TOKEN)

class StubRefreshAccessTokenServiceThatFails:
    def execute(self, token: str):
        # main.py 핸들러에서 401로 인식되는 메시지를 던짐
        raise ValueError(INVALID_TOKEN_MSG)

# 5. pytest fixture
@pytest.fixture
def api_client_with_refresh_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_refresh_token_service] = lambda: StubRefreshAccessTokenService()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = original

@pytest.fixture
def api_client_with_failing_refresh_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_refresh_token_service] = lambda: StubRefreshAccessTokenServiceThatFails()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = original

# 6 & 7. 테스트 클래스 및 함수
class TestRefreshAccessTokenApi:
    """UC-AUTH-006 - POST /auth/refresh"""

    def test_valid_refresh_token_returns_200_with_new_access_token(self, api_client_with_refresh_stub):
        # 성공 시 응답 스키마 검증
        response = api_client_with_refresh_stub.post(
            "/auth/refresh",
            params={"refresh_token": VALID_REFRESH_TOKEN}
        )
        assert response.status_code == 200
        body = response.json()
        assert "app_access_token" in body
        assert body["app_access_token"] == NEW_ACCESS_TOKEN

    def test_invalid_token_returns_401(self, api_client_with_failing_refresh_stub):
        # main.py의 exception_handler를 거쳐 401이 반환되는지 확인
        response = api_client_with_failing_refresh_stub.post(
            "/auth/refresh",
            params={"refresh_token": "invalid-token"}
        )
        assert response.status_code == 401
        assert response.json()["message"] == INVALID_TOKEN_MSG