"""
카드 검증과 card token 발급 API 테스트.
UC-CARDCO-001: POST /cards/verify
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_verify_and_tokenize_card_service
from app.application.card.verify_and_tokenize_card import (
    VerifyAndTokenizeCardResult,
)
from app.main import app


VALID_USER_ID = "user-001"
VALID_CARD_NUMBER = "1234567890123456"
VALID_EXPIRY = "12/28"
VALID_CVC = "123"
VALID_CARD_TOKEN = "card-token-001"
VALID_LAST_FOUR = "3456"


class StubVerifyAndTokenizeCardService:
    def execute(self, command):
        return VerifyAndTokenizeCardResult(
            card_token=VALID_CARD_TOKEN,
            last_four=VALID_LAST_FOUR,
        )


class StubVerifyAndTokenizeCardServiceThatFails:
    def execute(self, command):
        raise ValueError("invalid_card")


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_verify_and_tokenize_card_service] = (
        lambda: StubVerifyAndTokenizeCardService()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


@pytest.fixture
def api_client_with_failing_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_verify_and_tokenize_card_service] = (
        lambda: StubVerifyAndTokenizeCardServiceThatFails()
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def valid_verify_payload():
    return {
        "user_id": VALID_USER_ID,
        "card_number": VALID_CARD_NUMBER,
        "expiry": VALID_EXPIRY,
        "cvc": VALID_CVC,
    }


class TestVerifyAndTokenizeCardApi:
    """UC-CARDCO-001 - POST /cards/verify"""

    def test_valid_card_returns_card_token_and_last_four(
        self,
        api_client_with_service_stub,
    ):
        response = api_client_with_service_stub.post(
            "/cards/verify",
            json=valid_verify_payload(),
        )

        assert response.status_code == 200
        assert response.json() == {
            "card_token": VALID_CARD_TOKEN,
            "last_four": VALID_LAST_FOUR,
        }

    def test_duplicate_user_and_card_returns_existing_token(
        self,
        api_client_with_service_stub,
    ):
        first_response = api_client_with_service_stub.post(
            "/cards/verify",
            json=valid_verify_payload(),
        )
        second_response = api_client_with_service_stub.post(
            "/cards/verify",
            json=valid_verify_payload(),
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["card_token"] == VALID_CARD_TOKEN

    def test_expired_card_returns_400(self, api_client_with_failing_service_stub):
        response = api_client_with_failing_service_stub.post(
            "/cards/verify",
            json=valid_verify_payload(),
        )

        assert response.status_code == 400
        assert response.json()["message"] == "invalid_card"

    def test_missing_card_number_returns_422(self, api_client_with_service_stub):
        payload = valid_verify_payload()
        payload.pop("card_number")

        response = api_client_with_service_stub.post(
            "/cards/verify",
            json=payload,
        )

        assert response.status_code == 422
