"""
카드 등록 / Billing Key API 테스트
UC-CARD-002: POST /card/webhook
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_handle_card_webhook_service
from app.application.card.handle_card_webhook import HandleCardWebhookResult


# ──────────────────────────────────────────────
# 테스트 상수
# ──────────────────────────────────────────────

VALID_ORDER_ID = "order-abc-001"
VALID_BILLING_KEY = "bk-xyz-9999"
VALID_CARD_LAST_FOUR = "1234"
VALID_SIGNATURE = "valid-hmac-signature"
INVALID_SIGNATURE = "tampered-signature"


# ──────────────────────────────────────────────
# Stub 클래스
# ──────────────────────────────────────────────

class StubHandleCardWebhookService:
    def execute(self, command):
        return HandleCardWebhookResult(status="ok")


class StubHandleCardWebhookServiceThatFailsWithSignature:
    """signature 검증 실패 → 401
    openapi: '401': webhook signature 검증 실패
    service 레이어에서 PermissionError를 던지면 exception handler가 401로 변환한다.
    """
    def execute(self, command):
        raise PermissionError("invalid_signature")


class StubHandleCardWebhookServiceThatFailsWithOrder:
    """order 없음, 세션 검증 실패 등 비즈니스 오류 → 400
    openapi: '400': 유효하지 않은 세션 또는 검증 실패
    """
    def execute(self, command):
        raise ValueError("order_not_found")


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_card_webhook_service] = (
        lambda: StubHandleCardWebhookService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_signature_failing_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_card_webhook_service] = (
        lambda: StubHandleCardWebhookServiceThatFailsWithSignature()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_order_failing_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_handle_card_webhook_service] = (
        lambda: StubHandleCardWebhookServiceThatFailsWithOrder()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


# ──────────────────────────────────────────────
# 테스트 클래스
# ──────────────────────────────────────────────

class TestHandleCardWebhookApi:
    """UC-CARD-002 - POST /card/webhook"""

    # ── 성공 케이스 ──

    def test_valid_webhook_returns_200_with_ok_status(
        self,
        api_client_with_service_stub,
    ):
        """유효한 webhook이면 200과 status=ok를 반환한다."""
        response = api_client_with_service_stub.post(
            "/card/webhook",
            json={
                "order_id": VALID_ORDER_ID,
                "billing_key": VALID_BILLING_KEY,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "active",
                "signature": VALID_SIGNATURE,
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    # ── Request validation 케이스 ──

    def test_missing_order_id_returns_422(self, api_client_with_service_stub):
        """order_id가 누락되면 422를 반환한다."""
        response = api_client_with_service_stub.post(
            "/card/webhook",
            json={
                "billing_key": VALID_BILLING_KEY,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "active",
                "signature": VALID_SIGNATURE,
            },
        )

        assert response.status_code == 422

    def test_missing_billing_key_returns_422(self, api_client_with_service_stub):
        """billing_key가 누락되면 422를 반환한다."""
        response = api_client_with_service_stub.post(
            "/card/webhook",
            json={
                "order_id": VALID_ORDER_ID,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "active",
                "signature": VALID_SIGNATURE,
            },
        )

        assert response.status_code == 422

    def test_missing_signature_returns_422(self, api_client_with_service_stub):
        """signature가 누락되면 422를 반환한다."""
        response = api_client_with_service_stub.post(
            "/card/webhook",
            json={
                "order_id": VALID_ORDER_ID,
                "billing_key": VALID_BILLING_KEY,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "active",
            },
        )

        assert response.status_code == 422

    def test_invalid_status_enum_returns_422(self, api_client_with_service_stub):
        """status가 enum 값이 아니면 422를 반환한다."""
        response = api_client_with_service_stub.post(
            "/card/webhook",
            json={
                "order_id": VALID_ORDER_ID,
                "billing_key": VALID_BILLING_KEY,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "invalid_status",
                "signature": VALID_SIGNATURE,
            },
        )

        assert response.status_code == 422

    # ── 외부 호출 endpoint 보안 케이스 ──

    def test_invalid_signature_returns_401(
        self,
        api_client_with_signature_failing_stub,
    ):
        """signature가 틀리면 401을 반환한다."""
        response = api_client_with_signature_failing_stub.post(
            "/card/webhook",
            json={
                "order_id": VALID_ORDER_ID,
                "billing_key": VALID_BILLING_KEY,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "active",
                "signature": INVALID_SIGNATURE,
            },
        )

        assert response.status_code == 401
        assert response.json()["message"] == "invalid_signature"


    # ── 비즈니스 오류 케이스 ──

    def test_order_not_found_returns_400(
        self,
        api_client_with_order_failing_stub,
    ):
        """order가 없으면 400을 반환한다."""
        response = api_client_with_order_failing_stub.post(
            "/card/webhook",
            json={
                "order_id": VALID_ORDER_ID,
                "billing_key": VALID_BILLING_KEY,
                "card_last_four": VALID_CARD_LAST_FOUR,
                "status": "active",
                "signature": VALID_SIGNATURE,
            },
        )

        assert response.status_code == 400
        assert response.json()["message"] == "order_not_found"
