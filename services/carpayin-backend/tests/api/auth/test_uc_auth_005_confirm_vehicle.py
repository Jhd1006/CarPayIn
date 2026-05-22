"""
차량 확정 API 테스트
UC-AUTH-005: POST /auth/confirm-car
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app  # app 인스턴스 import
from app.api.deps import get_current_user_from_temp_token, get_confirm_car_service

# ═══════════════════════════════════════════════════════════════════════════
# 테스트 상수
# ═══════════════════════════════════════════════════════════════════════════

VALID_CAR_ID = "car-12345678"
VALID_VIN_HASH = "abc123def456"
VALID_APP_ACCESS_TOKEN = "app-access-token-xyz"
VALID_APP_REFRESH_TOKEN = "app-refresh-token-xyz"

# ═══════════════════════════════════════════════════════════════════════════
# Stub 클래스 (main.py의 에러 핸들러와 메시지 일치)
# ═══════════════════════════════════════════════════════════════════════════

class StubConfirmCarServiceSuccess:
    def execute(self, command):
        from dataclasses import dataclass
        @dataclass
        class ConfirmCarResult:
            car_id: str
            app_access_token: str
            app_refresh_token: str
            user_info: dict
            car_info: dict
        
        return ConfirmCarResult(
            car_id=command.car_id,
            app_access_token=VALID_APP_ACCESS_TOKEN,
            app_refresh_token=VALID_APP_REFRESH_TOKEN,
            user_info={"user_id": command.user_id},
            car_info={"car_id": command.car_id},
        )

class StubConfirmCarServiceCarNotFound:
    def execute(self, command):
        # main.py의 에러 핸들러에 맞춰 메시지 수정
        raise ValueError("car_id_not_in_hyundai_list")

class StubConfirmCarServiceVinMismatch:
    def execute(self, command):
        # main.py에는 정의되지 않았으므로 default 400으로 처리됨
        raise ValueError("vin_hash_mismatch")

# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

def fake_current_user():
    return {
        "user_id": "user-001",
        "session_id": "session-001",
        "access_token": "temp-token-001",
    }

@pytest.fixture
def client_factory():
    """테스트 간 독립성을 위해 dependency_overrides 관리"""
    original = app.dependency_overrides.copy()
    yield app
    app.dependency_overrides = original

@pytest.fixture
def api_client_authenticated(client_factory):
    app.dependency_overrides[get_current_user_from_temp_token] = fake_current_user
    app.dependency_overrides[get_confirm_car_service] = lambda: StubConfirmCarServiceSuccess()
    return TestClient(app)

@pytest.fixture
def api_client_car_not_found(client_factory):
    app.dependency_overrides[get_current_user_from_temp_token] = fake_current_user
    app.dependency_overrides[get_confirm_car_service] = lambda: StubConfirmCarServiceCarNotFound()
    return TestClient(app)

@pytest.fixture
def api_client_vin_mismatch(client_factory):
    app.dependency_overrides[get_current_user_from_temp_token] = fake_current_user
    app.dependency_overrides[get_confirm_car_service] = lambda: StubConfirmCarServiceVinMismatch()
    return TestClient(app)

# ═══════════════════════════════════════════════════════════════════════════
# 테스트 케이스
# ═══════════════════════════════════════════════════════════════════════════

class TestConfirmCarApi:
    def test_valid_request_returns_200(self, api_client_authenticated):
        response = api_client_authenticated.post(
            "/auth/confirm-car",
            headers={"Authorization": "Bearer temp-token-001"},
            json={"car_id": VALID_CAR_ID, "vin_hash": VALID_VIN_HASH},
        )
        assert response.status_code == 200

    # def test_car_id_not_in_list_returns_400(self, api_client_car_not_found):
    #     response = api_client_car_not_found.post(
    #         "/auth/confirm-car",
    #         headers={"Authorization": "Bearer temp-token-001"},
    #         json={"car_id": "bad-id", "vin_hash": VALID_VIN_HASH},
    #     )
    #     assert response.status_code == 400
    #     assert response.json()["message"] == "car_id_not_in_hyundai_list"

    def test_car_id_not_in_list_returns_400(self, api_client_car_not_found):
        response = api_client_car_not_found.post(
            "/auth/confirm-car",
            headers={"Authorization": "Bearer temp-token-001"},
            json={"car_id": "bad-id", "vin_hash": VALID_VIN_HASH},
        )
        
        # [핵심] 에러가 났을 때 실제로 서버가 준 응답 전체를 출력
        print(f"\n--- DEBUG RESPONSE ---")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.json()}")
        
        assert response.status_code == 400
        assert response.json()["message"] == "car_id_not_in_hyundai_list"

    def test_vin_hash_mismatch_returns_400(self, api_client_vin_mismatch):
        response = api_client_vin_mismatch.post(
            "/auth/confirm-car",
            headers={"Authorization": "Bearer temp-token-001"},
            json={"car_id": VALID_CAR_ID, "vin_hash": "wrong-hash"},
        )
        assert response.status_code == 400
        assert response.json()["message"] == "vin_hash_mismatch"