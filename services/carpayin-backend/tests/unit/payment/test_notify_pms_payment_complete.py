"""
요금 조회 / 결제 / 출차 유스케이스 단위 테스트
UC-PAY-003: 결제 완료 PMS 통보
"""

import pytest

from app.application.payment.notify_pms_payment_complete import (
    NotifyPmsPaymentCompleteCommand,
    NotifyPmsPaymentCompleteService,
)


VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_CARPAY_SESSION_ID = "parking-session-001"
VALID_TX_ID = "tx-123456"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_APPROVAL_NO = "APPR123456"
VALID_IDEMPOTENCY_KEY = "idem-key-001"


class FakeTransactionRepository:
    def __init__(self):
        self.transactions = {}

    def add_transaction(self, tx_id: str, status: str = "success"):
        self.transactions[tx_id] = {
            "tx_id": tx_id,
            "status": status,
        }

    def get_transaction_by_id(self, tx_id: str):
        return self.transactions.get(tx_id)


class FakePmsClient:
    def __init__(self):
        self.notify_calls = []
        self.should_timeout = False
        self.should_return_5xx = False
        self.should_conflict = False

    def notify_payment_complete(
        self,
        *,
        pms_session_id: str,
        carpay_session_id: str,
        tx_id: str,
        amount: int,
        currency: str,
        approval_no: str,
        idempotency_key: str,
    ) -> dict:
        if self.should_timeout:
            raise TimeoutError("PMS request timeout")

        if self.should_return_5xx:
            raise Exception("PMS 5xx server error")

        if self.should_conflict:
            return {"status": "conflict", "message": "idempotency_key already processed"}

        self.notify_calls.append(
            {
                "pms_session_id": pms_session_id,
                "carpay_session_id": carpay_session_id,
                "tx_id": tx_id,
                "amount": amount,
                "currency": currency,
                "approval_no": approval_no,
                "idempotency_key": idempotency_key,
            }
        )

        return {"status": "success"}


class FakeRetryEventStore:
    def __init__(self):
        self.retry_events = []

    def record_retry_event(
        self, *, event_type: str, tx_id: str, payload: dict, reason: str
    ):
        self.retry_events.append(
            {
                "event_type": event_type,
                "tx_id": tx_id,
                "payload": payload,
                "reason": reason,
            }
        )


@pytest.fixture
def fake_transaction_repository():
    return FakeTransactionRepository()


@pytest.fixture
def fake_pms_client():
    return FakePmsClient()


@pytest.fixture
def fake_retry_event_store():
    return FakeRetryEventStore()


@pytest.fixture
def notify_pms_payment_complete_service(
    fake_transaction_repository,
    fake_pms_client,
    fake_retry_event_store,
):
    return NotifyPmsPaymentCompleteService(
        transaction_repository=fake_transaction_repository,
        pms_client=fake_pms_client,
        retry_event_store=fake_retry_event_store,
    )


class TestNotifyPmsPaymentComplete:
    """UC-PAY-003 - 내부 client 호출: PMS POST /payment/complete"""

    def test_payment_success_generates_correct_payload(
        self,
        notify_pms_payment_complete_service,
        fake_transaction_repository,
        fake_pms_client,
    ):
        """결제 성공 후 PMS paid notify payload가 정확히 생성된다."""
        fake_transaction_repository.add_transaction(VALID_TX_ID, status="success")

        command = NotifyPmsPaymentCompleteCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            carpay_parking_session_id=VALID_CARPAY_SESSION_ID,
            carpay_tx_id=VALID_TX_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            approval_no=VALID_APPROVAL_NO,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = notify_pms_payment_complete_service.execute(command)

        # PMS 호출 확인
        assert len(fake_pms_client.notify_calls) == 1
        call = fake_pms_client.notify_calls[0]
        assert call["pms_session_id"] == VALID_PMS_SESSION_ID
        assert call["carpay_session_id"] == VALID_CARPAY_SESSION_ID
        assert call["tx_id"] == VALID_TX_ID
        assert call["amount"] == VALID_AMOUNT
        assert call["currency"] == VALID_CURRENCY
        assert call["approval_no"] == VALID_APPROVAL_NO
        assert call["idempotency_key"] == VALID_IDEMPOTENCY_KEY

        # 응답 확인
        assert result.status == "success"

    def test_pms_timeout_preserves_payment_and_records_retry(
        self,
        notify_pms_payment_complete_service,
        fake_transaction_repository,
        fake_pms_client,
        fake_retry_event_store,
    ):
        """PMS timeout 시 결제 성공은 보존되고 재시도 가능 상태가 남는다."""
        fake_transaction_repository.add_transaction(VALID_TX_ID, status="success")
        fake_pms_client.should_timeout = True

        command = NotifyPmsPaymentCompleteCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            carpay_parking_session_id=VALID_CARPAY_SESSION_ID,
            carpay_tx_id=VALID_TX_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            approval_no=VALID_APPROVAL_NO,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = notify_pms_payment_complete_service.execute(command)

        # transaction은 여전히 success
        tx = fake_transaction_repository.get_transaction_by_id(VALID_TX_ID)
        assert tx["status"] == "success"

        # 재시도 이벤트 기록됨
        assert len(fake_retry_event_store.retry_events) == 1
        retry_event = fake_retry_event_store.retry_events[0]
        assert retry_event["event_type"] == "pms_payment_notify"
        assert retry_event["tx_id"] == VALID_TX_ID
        assert "timeout" in retry_event["reason"].lower()

        # 응답에 실패 표시 (하지만 결제는 성공)
        assert result.status == "retry_scheduled"
        assert result.retry_reason is not None

    def test_pms_5xx_preserves_payment_and_records_retry(
        self,
        notify_pms_payment_complete_service,
        fake_transaction_repository,
        fake_pms_client,
        fake_retry_event_store,
    ):
        """PMS 5xx 응답 시 결제 성공은 보존되고 재시도 가능 상태가 남는다."""
        fake_transaction_repository.add_transaction(VALID_TX_ID, status="success")
        fake_pms_client.should_return_5xx = True

        command = NotifyPmsPaymentCompleteCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            carpay_parking_session_id=VALID_CARPAY_SESSION_ID,
            carpay_tx_id=VALID_TX_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            approval_no=VALID_APPROVAL_NO,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = notify_pms_payment_complete_service.execute(command)

        # transaction은 여전히 success
        tx = fake_transaction_repository.get_transaction_by_id(VALID_TX_ID)
        assert tx["status"] == "success"

        # 재시도 이벤트 기록됨
        assert len(fake_retry_event_store.retry_events) == 1
        retry_event = fake_retry_event_store.retry_events[0]
        assert retry_event["event_type"] == "pms_payment_notify"
        assert retry_event["tx_id"] == VALID_TX_ID
        assert "5xx" in retry_event["reason"] or "server error" in retry_event["reason"].lower()

        # 응답에 실패 표시
        assert result.status == "retry_scheduled"

    def test_duplicate_idempotency_key_is_safe(
        self,
        notify_pms_payment_complete_service,
        fake_transaction_repository,
        fake_pms_client,
    ):
        """같은 idempotency_key로 PMS 통보가 중복되어도 안전하다."""
        fake_transaction_repository.add_transaction(VALID_TX_ID, status="success")
        fake_pms_client.should_conflict = True

        command = NotifyPmsPaymentCompleteCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            carpay_parking_session_id=VALID_CARPAY_SESSION_ID,
            carpay_tx_id=VALID_TX_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            approval_no=VALID_APPROVAL_NO,
            idempotency_key=VALID_IDEMPOTENCY_KEY,
        )

        result = notify_pms_payment_complete_service.execute(command)

        # PMS가 conflict를 반환해도 안전하게 처리
        assert result.status == "already_processed"

        # transaction은 여전히 success
        tx = fake_transaction_repository.get_transaction_by_id(VALID_TX_ID)
        assert tx["status"] == "success"