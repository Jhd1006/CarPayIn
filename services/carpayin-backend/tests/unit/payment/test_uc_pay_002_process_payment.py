"""
요금 조회 / 결제 / 출차 유스케이스 단위 테스트
UC-PAY-002: 결제 요청 처리
"""

import pytest
import hashlib

from app.application.payment.process_payment import (
    ProcessPaymentCommand,
    ProcessPaymentService,
)


VALID_ACCESS_TOKEN = "at_valid_token_001"
VALID_SESSION_ID = "parking-session-001"
VALID_CAR_ID = "car-001"
VALID_USER_ID = "user-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_AMOUNT = 5000
VALID_CURRENCY = "KRW"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"
#추가된 item
VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_BILLING_KEY = "bk-001"
VALID_APPROVAL_NO = "APPR123456"


class FakeTokenValidator:
    def __init__(self):
        self.valid_tokens = {
            VALID_ACCESS_TOKEN: {
                "user_id": VALID_USER_ID,
                "car_id": VALID_CAR_ID,
            }
        }

    def validate_and_extract(self, access_token: str) -> dict:
        if access_token not in self.valid_tokens:
            raise ValueError("invalid_token")
        return self.valid_tokens[access_token]


class FakeFeeQuoteStore:
    def __init__(self):
        self.quotes = {}

    def add_quote(self, session_id: str, amount: int, currency: str):
        self.quotes[session_id] = {
            "session_id": session_id,
            "amount": amount,
            "currency": currency,
        }

    def get_quote(self, session_id: str):
        return self.quotes.get(session_id)


class FakeParkingSessionRepository:
    def __init__(self):
        self.sessions = {}

    def add_session(
        self,
        session_id: str,
        car_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
        status: str = "active",
        pms_session_id: str = VALID_PMS_SESSION_ID,
    ):
        self.sessions[session_id] = {
            "session_id": session_id,
            "car_id": car_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
            "status": status,
            "pms_session_id": pms_session_id,
        }

    def get_session_by_id(self, session_id: str):
        return self.sessions.get(session_id)

    def update_session_status(self, session_id: str, status: str):
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = status


class FakeBillingKeyRepository:
    def __init__(self):
        self.billing_keys = {}

    def add_active_billing_key(
            self, car_id: str, billing_key: str = VALID_BILLING_KEY):
        self.billing_keys[car_id] = {
            "car_id": car_id,
            "billing_key": billing_key,
            "status": "active",
        }

    def get_active_billing_key(self, car_id: str):
        key = self.billing_keys.get(car_id)
        if key and key["status"] == "active":
            return key
        return None


class FakeTransactionRepository:
    def __init__(self):
        self.transactions = {}

    def get_transaction_by_idempotency_key(self, idempotency_key: str):
        return self.transactions.get(idempotency_key)

    def create_pending_transaction(
        self, *, tx_id: str, idempotency_key: str, session_id: str, amount: int, currency: str, billing_key: str,
    ):
        self.transactions[idempotency_key] = {
            "tx_id": tx_id,
            "idempotency_key": idempotency_key,
            "session_id": session_id,
            "amount": amount,
            "currency": currency,
            "billing_key": billing_key,
            "status": "pending",
        }

    def update_transaction_status(
        self, idempotency_key: str, status: str, pg_tx_id: str = None, approval_no: str = None, failed_reason: str = None
    ):
        if idempotency_key in self.transactions:
            self.transactions[idempotency_key]["status"] = status
            if pg_tx_id:
                self.transactions[idempotency_key]["pg_tx_id"] = pg_tx_id
            if approval_no:
                self.transactions[idempotency_key]["approval_no"] = approval_no
            if failed_reason:
                self.transactions[idempotency_key]["failed_reason"] = failed_reason

class FakePgClient:
    def __init__(self):
        self.payment_requests = []
        self.should_fail = False


    def charge_billing_key(
        self, *, billing_key: str, amount: int, currency: str, idempotency_key: str
    ) -> dict:

        self.payment_requests.append(
            {
                "billing_key": billing_key,
                "amount": amount,
                "currency": currency,
                "idempotency_key": idempotency_key,
            }
        )

        if self.should_fail:
            return {
                "success": False,
                "pg_tx_id": "pg-tx-failed-001",
                "failed_reason": "PG payment failed",
            }
        
        return {
            "success": True,
            "pg_tx_id": "pg-tx-001",
            "approval_no": VALID_APPROVAL_NO,
        }


class FakePmsClient:
    def __init__(self):
        self.notify_calls = []
        self.should_fail = False

    def notify_payment_complete(
        self, *, pms_session_id: str, carpay_parking_session_id: str, carpay_tx_id: str, amount: int, currency: str, approval_no: str, idempotency_key: str,
    ):
        if self.should_fail:
            raise Exception("PMS notify failed")

        self.notify_calls.append(
            {
                "pms_session_id": pms_session_id,
                "carpay_parking_session_id": carpay_parking_session_id,
                "carpay_tx_id": carpay_tx_id,
                "amount": amount,
                "currency": currency,
                "approval_no": approval_no,
                "idempotency_key": idempotency_key,
            }
        )


class FakeNotificationPublisher:
    def __init__(self):
        self.published_messages = []

    def publish_payment_notification(
        self, *, session_id: str, car_id: str, lot_id: str, tx_id: str, amount: int, currency: str, approval_no: str
    ):
        self.published_messages.append(
            {
                "type": "payment_complete",
                "session_id": session_id,
                "car_id": car_id,
                "lot_id": lot_id,
                "tx_id": tx_id,
                "amount": amount,
                "currency": currency,
                "approval_no": approval_no,
            }
        )

def _make_idempotency_key(
    session_id: str, car_id: str, amount: int, currency: str
) -> str:
    return hashlib.sha256(
        f"{session_id}{car_id}{amount}{currency}".encode()
    ).hexdigest()


@pytest.fixture
def fake_token_validator():
    return FakeTokenValidator()


@pytest.fixture
def fake_fee_quote_store():
    return FakeFeeQuoteStore()


@pytest.fixture
def fake_parking_session_repository():
    return FakeParkingSessionRepository()


@pytest.fixture
def fake_billing_key_repository():
    return FakeBillingKeyRepository()


@pytest.fixture
def fake_transaction_repository():
    return FakeTransactionRepository()


@pytest.fixture
def fake_pg_client():
    return FakePgClient()


@pytest.fixture
def fake_pms_client():
    return FakePmsClient()


@pytest.fixture
def fake_notification_publisher():
    return FakeNotificationPublisher()


@pytest.fixture
def process_payment_service(
    fake_token_validator,
    fake_fee_quote_store,
    fake_parking_session_repository,
    fake_billing_key_repository,
    fake_transaction_repository,
    fake_pg_client,
    fake_pms_client,
    fake_notification_publisher,
):
    return ProcessPaymentService(
        token_validator=fake_token_validator,
        fee_quote_store=fake_fee_quote_store,
        parking_session_repository=fake_parking_session_repository,
        billing_key_repository=fake_billing_key_repository,
        transaction_repository=fake_transaction_repository,
        pg_client=fake_pg_client,
        pms_client=fake_pms_client,
        notification_publisher=fake_notification_publisher,
    )


class TestProcessPayment:
    """UC-PAY-002 - POST /payment"""

    #추가한 함수
    def test_invalid_access_token_raises_error(self, process_payment_service):
        """유효하지 않은 access token이면 인증 오류를 반환한다."""
        command = ProcessPaymentCommand(
            access_token="invalid-token",
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )
 
        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)
 
        assert str(exc_info.value) == "invalid_token"

    def test_quote_not_found_raises_error(self, process_payment_service):
        """quote가 없으면 quote_not_found 오류를 반환한다."""
        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "quote_not_found"

    def test_amount_mismatch_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
    ):
        """amount가 quote와 다르면 amount_currency_mismatch 오류를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, 3000, VALID_CURRENCY)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "amount_currency_mismatch"

    #amount와 currency 분리해서 작성
    def test_currency_mismatch_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
    ):
        """currency가 quote와 다르면 amount_currency_mismatch 오류를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, "USD")
 
        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )
 
        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)
 
        assert str(exc_info.value) == "amount_currency_mismatch"

    def test_session_not_found_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
    ):
        """session이 없으면 session_not_found 오류를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "session_not_found"

    def test_session_car_id_mismatch_raises_error(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
    ):
        """session 소유 차량과 token 차량이 다르면 session_car_id_mismatch 오류를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id="other-car-id",
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "session_car_id_mismatch"

    def test_no_active_billing_key_raises_error_and_does_not_call_pg(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_pg_client,
    ):
        """active billing key가 없으면 no_active_billing_key 오류를 반환하고 PG를 호출하지 않는다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        with pytest.raises(ValueError) as exc_info:
            process_payment_service.execute(command)

        assert str(exc_info.value) == "no_active_billing_key"
        assert len(fake_pg_client.payment_requests) == 0

    def test_valid_request_creates_pending_transaction_and_calls_pg(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pg_client,
    ):
        """quote 금액과 요청 금액이 같으면 pending transaction을 만들고 PG를 호출한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        process_payment_service.execute(command)

        # pending transaction 생성 확인
        idempotency_key = _make_idempotency_key(
            VALID_SESSION_ID, VALID_CAR_ID, VALID_AMOUNT, VALID_CURRENCY
        )
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(
            idempotency_key
        )
        assert tx is not None
        assert len(fake_pg_client.payment_requests) == 1
        assert fake_pg_client.payment_requests[0]["billing_key"] == VALID_BILLING_KEY
        assert fake_pg_client.payment_requests[0]["amount"] == VALID_AMOUNT
        assert fake_pg_client.payment_requests[0]["currency"] == VALID_CURRENCY

    def test_pg_success_updates_transaction_and_completes_session(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pms_client,
        fake_notification_publisher,
    ):
        """PG 성공이면 transaction success, parking session completed가 되고 PMS 통보와 알림이 발행된다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        result = process_payment_service.execute(command)

        idempotency_key = _make_idempotency_key(
            VALID_SESSION_ID, VALID_CAR_ID, VALID_AMOUNT, VALID_CURRENCY
        )
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(
            idempotency_key
        )
        assert tx["status"] == "success"
        assert tx["approval_no"] == VALID_APPROVAL_NO

        # parking session completed 확인
        session = fake_parking_session_repository.get_session_by_id(VALID_SESSION_ID)
        assert session["status"] == "completed"

        # PMS notify 호출 확인
        assert len(fake_pms_client.notify_calls) == 1

        # 알림 발행 확인
        assert len(fake_notification_publisher.published_messages) == 1

        # 응답 확인
        assert result.status == "success"
        assert result.tx_id is not None
        assert result.approval_no == VALID_APPROVAL_NO

    def test_pg_failure_marks_transaction_failed_and_keeps_session_active(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pg_client,
        fake_pms_client,
    ):
        """PG 실패이면 transaction failed, parking session active가 유지되고 PMS 통보가 없다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)
        fake_pg_client.should_fail = True

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        result = process_payment_service.execute(command)

        # transaction failed 확인
        idempotency_key = _make_idempotency_key(
            VALID_SESSION_ID, VALID_CAR_ID, VALID_AMOUNT, VALID_CURRENCY
        )
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(
            idempotency_key
        )
        assert tx["status"] == "failed"


        # parking session active 유지 확인
        session = fake_parking_session_repository.get_session_by_id(VALID_SESSION_ID)
        assert session["status"] == "active"

        assert len(fake_pms_client.notify_calls) == 0

        # 응답 확인
        assert result.status == "failed"
        assert result.failed_reason is not None

    def test_duplicate_idempotency_key_returns_existing_result_without_calilng_pg_again(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_pg_client,
    ):
        """같은 idempotency_key로 재요청하면 PG를 다시 호출하지 않고 기존 결과를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        # 첫 번째 요청
        first_result = process_payment_service.execute(command)

        # 두 번째 요청
        second_result = process_payment_service.execute(command)

        # 같은 결과 반환
        assert first_result.tx_id == second_result.tx_id
        assert first_result.approval_no == second_result.approval_no

        # PG가 한 번만 호출됨
        assert len(fake_pg_client.payment_requests) == 1

    def test_pending_transaction_returns_pending_status_without_calling_pg_again(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pms_client,
    ):
        """pending transaction이 있으면 PG를 다시 호출하지 않고 pending 상태를 반환한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)

        idempotency_key = _make_idempotency_key(
            VALID_SESSION_ID, VALID_CAR_ID, VALID_AMOUNT, VALID_CURRENCY
        )
        fake_transaction_repository.create_pending_transaction(
            tx_id="tx-pending-001",
            idempotency_key=idempotency_key,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
            billing_key=VALID_BILLING_KEY,
        )

        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )

        result = process_payment_service.execute(command)

        assert result.status == "pending"
        assert len(fake_pg_client.payment_requests) == 0

 
    def test_pms_notify_failure_keeps_payment_success(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_transaction_repository,
        fake_pms_client,
    ):
        """PMS 통보 실패 시 결제 성공은 유지되고 transaction은 success 상태를 유지한다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)
        fake_pms_client.should_fail = True
 
        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )
 
        result = process_payment_service.execute(command)
 
        assert result.status == "success"
        assert result.approval_no is not None

        idempotency_key = _make_idempotency_key(
            VALID_SESSION_ID, VALID_CAR_ID, VALID_AMOUNT, VALID_CURRENCY
        )
        tx = fake_transaction_repository.get_transaction_by_idempotency_key(
            idempotency_key
        )
        assert tx["status"] == "success"
 
        session = fake_parking_session_repository.get_session_by_id(VALID_SESSION_ID)
        assert session["status"] == "completed"
 
    def test_notification_publish_called_with_correct_payload(
        self,
        process_payment_service,
        fake_fee_quote_store,
        fake_parking_session_repository,
        fake_billing_key_repository,
        fake_notification_publisher,
    ):
        """결제 성공 시 MQTT 알림이 올바른 payload로 발행된다."""
        fake_fee_quote_store.add_quote(VALID_SESSION_ID, VALID_AMOUNT, VALID_CURRENCY)
        fake_parking_session_repository.add_session(
            session_id=VALID_SESSION_ID,
            car_id=VALID_CAR_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )
        fake_billing_key_repository.add_active_billing_key(VALID_CAR_ID)
 
        command = ProcessPaymentCommand(
            access_token=VALID_ACCESS_TOKEN,
            session_id=VALID_SESSION_ID,
            amount=VALID_AMOUNT,
            currency=VALID_CURRENCY,
        )
 
        process_payment_service.execute(command)
 
        assert len(fake_notification_publisher.published_messages) == 1
        msg = fake_notification_publisher.published_messages[0]
        assert msg["session_id"] == VALID_SESSION_ID
        assert msg["car_id"] == VALID_CAR_ID
        assert msg["lot_id"] == VALID_LOT_ID
        assert msg["amount"] == VALID_AMOUNT
        assert msg["currency"] == VALID_CURRENCY
        assert msg["approval_no"] == VALID_APPROVAL_NO