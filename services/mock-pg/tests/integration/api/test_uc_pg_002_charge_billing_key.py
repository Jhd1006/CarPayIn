"""
UC-PG-002 통합 테스트: billing key 결제 승인
실제 DB에 데이터를 저장하고 조회한다.
외부 HTTP 클라이언트(Mock Card)는 스텁으로 대체한다.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_charge_billing_key_service
from app.application.pg.charge_billing_key import ChargeBillingKeyService
from app.infra.db.models import BillingKey, PGTransaction
from app.infra.db.session import SessionLocal
from app.infra.repositories.billing_key_repository import SqlAlchemyBillingKeyRepository
from app.infra.repositories.transaction_repository import SqlAlchemyTransactionRepository
from app.main import app


class StubMockCardClient:
    def __init__(self, *, should_fail: bool = False):
        self.should_fail = should_fail

    def approve_payment(self, *, card_token, amount, currency, idempotency_key):
        if self.should_fail:
            raise RuntimeError("card_approval_failed")
        return {
            "status": "success",
            "tx_id": f"card-tx-{uuid4().hex[:8]}",
            "approval_no": f"APPR{uuid4().hex[:8].upper()}",
        }


def _make_service_dep(stub_card_client):
    def _dep():
        session = SessionLocal()
        try:
            yield ChargeBillingKeyService(
                billing_key_repository=SqlAlchemyBillingKeyRepository(session),
                transaction_repository=SqlAlchemyTransactionRepository(session),
                mock_card_client=stub_card_client,
            )
        finally:
            session.close()

    return _dep


@pytest.fixture
def success_client():
    stub = StubMockCardClient(should_fail=False)
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_charge_billing_key_service] = _make_service_dep(stub)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides = original


def _insert_billing_key(billing_key: str, order_id: str, status: str = "active") -> None:
    """테스트용 billing_key를 DB에 직접 삽입한다."""
    session = SessionLocal()
    try:
        repo = SqlAlchemyBillingKeyRepository(session)
        repo.save_billing_key(
            order_id=order_id,
            billing_key=billing_key,
            card_token=f"integ-token-{uuid4().hex[:8]}",
            last_four="3456",
        )
        if status == "inactive":
            record = session.get(BillingKey, billing_key)
            record.status = "inactive"
            session.commit()
    finally:
        session.close()


def _delete_by_billing_key(billing_key: str) -> None:
    """billing_key와 연관된 transactions를 포함해 정리한다."""
    session = SessionLocal()
    try:
        txs = session.scalars(
            select(PGTransaction).where(PGTransaction.billing_key == billing_key)
        ).all()
        for tx in txs:
            session.delete(tx)
        record = session.get(BillingKey, billing_key)
        if record is not None:
            session.delete(record)
        session.commit()
    finally:
        session.close()


class TestChargeBillingKeyIntegration:
    """UC-PG-002 - billing key 결제 승인 통합 테스트"""

    def test_billing_payment_saves_success_transaction_to_db(self, success_client):
        """active billing_key로 결제 요청 시 transaction이 success 상태로 DB에 저장된다."""
        billing_key = f"integ-bk-{uuid4().hex[:12]}"
        order_id = f"integ-order-{uuid4().hex[:12]}"
        idempotency_key = f"integ-idem-{uuid4().hex[:12]}"
        _insert_billing_key(billing_key, order_id)

        try:
            response = success_client.post(
                "/payments/billing",
                json={
                    "billing_key": billing_key,
                    "amount": 5000,
                    "currency": "KRW",
                    "idempotency_key": idempotency_key,
                },
            )

            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "success"
            assert body["pg_tx_id"] is not None
            assert body["approval_no"] is not None

            session = SessionLocal()
            try:
                tx = session.scalar(
                    select(PGTransaction).where(
                        PGTransaction.idempotency_key == idempotency_key
                    )
                )
                assert tx is not None
                assert tx.status == "success"
                assert tx.billing_key == billing_key
                assert tx.amount == 5000
                assert tx.approval_no == body["approval_no"]
                assert tx.card_tx_id is not None
            finally:
                session.close()
        finally:
            _delete_by_billing_key(billing_key)

    def test_duplicate_idempotency_key_creates_only_one_transaction_in_db(
        self, success_client
    ):
        """같은 idempotency_key로 두 번 요청해도 DB에 transaction이 하나만 생성된다."""
        billing_key = f"integ-bk-{uuid4().hex[:12]}"
        order_id = f"integ-order-{uuid4().hex[:12]}"
        idempotency_key = f"integ-idem-{uuid4().hex[:12]}"
        _insert_billing_key(billing_key, order_id)

        payload = {
            "billing_key": billing_key,
            "amount": 5000,
            "currency": "KRW",
            "idempotency_key": idempotency_key,
        }
        try:
            first = success_client.post("/payments/billing", json=payload)
            second = success_client.post("/payments/billing", json=payload)

            assert first.status_code == 200
            assert second.status_code == 200
            assert first.json()["pg_tx_id"] == second.json()["pg_tx_id"]

            session = SessionLocal()
            try:
                count = session.scalar(
                    select(func.count())
                    .select_from(PGTransaction)
                    .where(PGTransaction.idempotency_key == idempotency_key)
                )
                assert count == 1
            finally:
                session.close()
        finally:
            _delete_by_billing_key(billing_key)

    def test_inactive_billing_key_saves_failed_transaction_to_db(self, success_client):
        """inactive billing_key로 결제 요청 시 transaction이 failed 상태로 DB에 저장된다."""
        billing_key = f"integ-bk-{uuid4().hex[:12]}"
        order_id = f"integ-order-{uuid4().hex[:12]}"
        idempotency_key = f"integ-idem-{uuid4().hex[:12]}"
        _insert_billing_key(billing_key, order_id, status="inactive")

        try:
            response = success_client.post(
                "/payments/billing",
                json={
                    "billing_key": billing_key,
                    "amount": 5000,
                    "currency": "KRW",
                    "idempotency_key": idempotency_key,
                },
            )

            assert response.status_code == 400
            assert response.json()["status"] == "failed"

            session = SessionLocal()
            try:
                tx = session.scalar(
                    select(PGTransaction).where(
                        PGTransaction.idempotency_key == idempotency_key
                    )
                )
                assert tx is not None
                assert tx.status == "failed"
                assert tx.failed_reason == "inactive_billing_key"
            finally:
                session.close()
        finally:
            _delete_by_billing_key(billing_key)
