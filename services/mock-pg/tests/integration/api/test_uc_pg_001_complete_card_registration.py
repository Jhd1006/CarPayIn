"""
UC-PG-001 통합 테스트: 카드 등록 WebView 완료와 billing key 발급
실제 DB에 데이터를 저장하고 조회한다.
외부 HTTP 클라이언트(Mock Card, CarPayIn webhook)는 스텁으로 대체한다.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_complete_card_registration_service
from app.application.pg.complete_card_registration import CompleteCardRegistrationService
from app.infra.db.models import BillingKey
from app.infra.db.session import SessionLocal
from app.infra.repositories.billing_key_repository import SqlAlchemyBillingKeyRepository
from app.main import app


class StubMockCardClient:
    def __init__(self, *, should_fail: bool = False):
        self.should_fail = should_fail

    def verify_and_tokenize_card(self, *, user_id, card_number, expiry, cvc):
        if self.should_fail:
            raise RuntimeError("card_verification_failed")
        return {
            "card_token": f"integ-token-{uuid4().hex[:8]}",
            "last_four": card_number[-4:],
        }


class StubCarPayInWebhookClient:
    def send_card_registration_webhook(self, *, order_id, billing_key, last_four):
        pass


def _make_service_dep(stub_card_client):
    def _dep():
        session = SessionLocal()
        try:
            yield CompleteCardRegistrationService(
                mock_card_client=stub_card_client,
                billing_key_repository=SqlAlchemyBillingKeyRepository(session),
                carpayin_webhook_client=StubCarPayInWebhookClient(),
            )
        finally:
            session.close()

    return _dep


@pytest.fixture
def success_client():
    stub = StubMockCardClient(should_fail=False)
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_complete_card_registration_service] = _make_service_dep(stub)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = original


@pytest.fixture
def failure_client():
    stub = StubMockCardClient(should_fail=True)
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_complete_card_registration_service] = _make_service_dep(stub)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = original


def _delete_billing_key_by_order(order_id: str) -> None:
    session = SessionLocal()
    try:
        record = session.scalar(
            select(BillingKey).where(BillingKey.order_id == order_id)
        )
        if record is not None:
            session.delete(record)
            session.commit()
    finally:
        session.close()


class TestCardRegistrationIntegration:
    """UC-PG-001 - 카드 등록 WebView 완료와 billing key 발급 통합 테스트"""

    def test_card_registration_saves_billing_key_to_db(self, success_client):
        """카드 등록 성공 시 billing_key가 DB에 active 상태로 저장된다."""
        order_id = f"integ-order-{uuid4().hex[:12]}"
        try:
            response = success_client.post(
                "/card-register",
                json={
                    "order_id": order_id,
                    "card_number": "1234567890123456",
                    "expiry": "12/28",
                    "cvc": "123",
                },
            )

            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "success"
            billing_key = body["billing_key"]
            assert billing_key is not None

            session = SessionLocal()
            try:
                record = session.scalar(
                    select(BillingKey).where(BillingKey.order_id == order_id)
                )
                assert record is not None
                assert record.billing_key == billing_key
                assert record.card_last_four == "3456"
                assert record.status == "active"
            finally:
                session.close()
        finally:
            _delete_billing_key_by_order(order_id)

    def test_duplicate_order_id_creates_only_one_billing_key_in_db(self, success_client):
        """같은 order_id로 두 번 요청해도 DB에 billing_key 레코드가 하나만 생성된다."""
        order_id = f"integ-order-{uuid4().hex[:12]}"
        payload = {
            "order_id": order_id,
            "card_number": "1234567890123456",
            "expiry": "12/28",
            "cvc": "123",
        }
        try:
            first = success_client.post("/card-register", json=payload)
            second = success_client.post("/card-register", json=payload)

            assert first.status_code == 200
            assert second.status_code == 200
            assert first.json()["billing_key"] == second.json()["billing_key"]

            session = SessionLocal()
            try:
                count = session.scalar(
                    select(func.count())
                    .select_from(BillingKey)
                    .where(BillingKey.order_id == order_id)
                )
                assert count == 1
            finally:
                session.close()
        finally:
            _delete_billing_key_by_order(order_id)

    def test_card_verification_failure_does_not_save_billing_key_to_db(self, failure_client):
        """카드 검증 실패 시 DB에 billing_key가 저장되지 않는다."""
        order_id = f"integ-order-{uuid4().hex[:12]}"

        response = failure_client.post(
            "/card-register",
            json={
                "order_id": order_id,
                "card_number": "1234567890123456",
                "expiry": "12/28",
                "cvc": "123",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "failed"

        session = SessionLocal()
        try:
            record = session.scalar(
                select(BillingKey).where(BillingKey.order_id == order_id)
            )
            assert record is None
        finally:
            session.close()
