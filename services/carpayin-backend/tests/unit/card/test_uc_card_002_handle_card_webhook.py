"""
카드 등록 / Billing Key 유스케이스 단위 테스트
UC-CARD-002: 카드 등록 완료 webhook 처리
"""

import pytest

from app.application.card.handle_card_webhook import (
    HandleCardWebhookCommand,
    HandleCardWebhookService,
)


# ──────────────────────────────────────────────
# 테스트 상수
# ──────────────────────────────────────────────

VALID_ORDER_ID = "order-abc-001"
VALID_BILLING_KEY = "bk-xyz-9999"
VALID_CARD_LAST_FOUR = "1234"
VALID_SIGNATURE = "valid-hmac-signature"
VALID_CAR_ID = "car-001"

INVALID_SIGNATURE = "tampered-signature"
INVALID_CARD_LAST_FOUR_TOO_LONG = "12345"
INVALID_CARD_LAST_FOUR_NON_NUMERIC = "12AB"

OTHER_BILLING_KEY = "bk-other-0001"

EXPIRED_ORDER_ID = "order-expired-999"


# ──────────────────────────────────────────────
# Fake 클래스
# ──────────────────────────────────────────────

class FakeCardOrderStore:
    def __init__(self, *, pending_order_id: str = VALID_ORDER_ID, car_id: str = VALID_CAR_ID):
        self._pending: dict[str, dict] = {
            pending_order_id: {"status": "pending", "car_id": car_id},
        }
        self.deleted_order_ids: list[str] = []
        self.completed_order_ids: list[str] = []

    def get_pending(self, *, order_id: str) -> dict | None:
        entry = self._pending.get(order_id)
        if entry and entry["status"] == "pending":
            return entry
        return None

    def mark_complete(self, *, order_id: str) -> None:
        if order_id in self._pending:
            self._pending[order_id]["status"] = "complete"
            self.completed_order_ids.append(order_id)

    def delete(self, *, order_id: str) -> None:
        self._pending.pop(order_id, None)
        self.deleted_order_ids.append(order_id)


class FakeBillingKeyRepository:
    def __init__(self):
        self.saved_keys: dict[str, dict] = {}  # car_id -> billing key info

    def upsert(self, *, car_id: str, billing_key: str, card_last_four: str) -> None:
        self.saved_keys[car_id] = {
            "billing_key": billing_key,
            "card_last_four": card_last_four,
            "status": "active",
        }

    def find_by_car_id(self, *, car_id: str) -> dict | None:
        return self.saved_keys.get(car_id)


class FakeVehicleRepository:
    def __init__(self, *, existing_car_ids: list[str] | None = None):
        self._existing_car_ids: set[str] = set(existing_car_ids or [VALID_CAR_ID])

    def exists_by_car_id(self, *, car_id: str) -> bool:
        return car_id in self._existing_car_ids


class FakeSignatureVerifier:
    def __init__(self, *, valid_signature: str = VALID_SIGNATURE):
        self._valid_signature = valid_signature
        self.verify_calls: list[dict] = []

    def verify(self, *, order_id: str, signature: str) -> bool:
        self.verify_calls.append({"order_id": order_id, "signature": signature})
        return signature == self._valid_signature


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def fake_card_order_store():
    return FakeCardOrderStore()


@pytest.fixture
def fake_billing_key_repo():
    return FakeBillingKeyRepository()


@pytest.fixture
def fake_vehicle_repo():
    return FakeVehicleRepository()


@pytest.fixture
def fake_signature_verifier():
    return FakeSignatureVerifier()


@pytest.fixture
def handle_card_webhook_service(
    fake_card_order_store,
    fake_billing_key_repo,
    fake_vehicle_repo,
    fake_signature_verifier,
):
    return HandleCardWebhookService(
        card_order_store=fake_card_order_store,
        billing_key_repository=fake_billing_key_repo,
        vehicle_repository=fake_vehicle_repo,
        signature_verifier=fake_signature_verifier,
    )


# ──────────────────────────────────────────────
# 테스트 클래스
# ──────────────────────────────────────────────

class TestHandleCardWebhook:
    """UC-CARD-002 - POST /card/webhook"""

    # ── 성공 케이스 ──

    def test_valid_webhook_saves_active_billing_key(
        self,
        handle_card_webhook_service,
        fake_billing_key_repo,
    ):
        """정상 webhook이면 vehicle_billing_keys에 active billing key를 저장한다."""
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=VALID_SIGNATURE,
        )

        handle_card_webhook_service.execute(command)

        saved = fake_billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID)
        assert saved is not None
        assert saved["billing_key"] == VALID_BILLING_KEY
        assert saved["card_last_four"] == VALID_CARD_LAST_FOUR
        assert saved["status"] == "active"

    def test_valid_webhook_completes_or_deletes_order_from_store(
        self,
        handle_card_webhook_service,
        fake_card_order_store,
    ):
        """정상 webhook 처리 후 Redis order를 complete 처리하거나 삭제한다."""
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=VALID_SIGNATURE,
        )

        handle_card_webhook_service.execute(command)

        order_cleared = (
            VALID_ORDER_ID in fake_card_order_store.completed_order_ids
            or VALID_ORDER_ID in fake_card_order_store.deleted_order_ids
        )
        assert order_cleared

    def test_duplicate_webhook_does_not_corrupt_billing_key(
        self,
        handle_card_webhook_service,
        fake_billing_key_repo,
    ):
        """같은 webhook이 두 번 와도 billing key 상태가 깨지지 않는다."""
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=VALID_SIGNATURE,
        )

        handle_card_webhook_service.execute(command)
        handle_card_webhook_service.execute(command)

        saved = fake_billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID)
        assert saved is not None
        assert saved["billing_key"] == VALID_BILLING_KEY
        assert saved["status"] == "active"

    def test_valid_webhook_replaces_existing_billing_key(
        self,
        fake_card_order_store,
        fake_vehicle_repo,
        fake_signature_verifier,
    ):
        """이미 billing key가 있는 차량이면 새 값으로 교체한다."""
        billing_key_repo = FakeBillingKeyRepository()
        billing_key_repo.upsert(
            car_id=VALID_CAR_ID,
            billing_key=OTHER_BILLING_KEY,
            card_last_four="0000",
        )
        service = HandleCardWebhookService(
            card_order_store=fake_card_order_store,
            billing_key_repository=billing_key_repo,
            vehicle_repository=fake_vehicle_repo,
            signature_verifier=fake_signature_verifier,
        )
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=VALID_SIGNATURE,
        )

        service.execute(command)

        saved = billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID)
        assert saved["billing_key"] == VALID_BILLING_KEY
        assert saved["card_last_four"] == VALID_CARD_LAST_FOUR

    # ── 실패 케이스 ──

    def test_invalid_signature_raises_error(
        self,
        fake_card_order_store,
        fake_billing_key_repo,
        fake_vehicle_repo,
    ):
        """signature가 틀리면 오류를 발생시키고 billing key를 저장하지 않는다."""
        verifier_that_rejects = FakeSignatureVerifier(valid_signature=VALID_SIGNATURE)
        service = HandleCardWebhookService(
            card_order_store=fake_card_order_store,
            billing_key_repository=fake_billing_key_repo,
            vehicle_repository=fake_vehicle_repo,
            signature_verifier=verifier_that_rejects,
        )
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=INVALID_SIGNATURE,
        )

        with pytest.raises(ValueError) as exc_info:
            service.execute(command)

        assert "signature" in str(exc_info.value).lower()
        assert fake_billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID) is None

    def test_order_not_found_raises_error(
        self,
        fake_billing_key_repo,
        fake_vehicle_repo,
        fake_signature_verifier,
    ):
        """order가 Redis에 없으면 오류를 발생시킨다."""
        empty_order_store = FakeCardOrderStore(pending_order_id="order-other-000")
        service = HandleCardWebhookService(
            card_order_store=empty_order_store,
            billing_key_repository=fake_billing_key_repo,
            vehicle_repository=fake_vehicle_repo,
            signature_verifier=fake_signature_verifier,
        )
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=VALID_SIGNATURE,
        )

        with pytest.raises(ValueError) as exc_info:
            service.execute(command)

        assert "order" in str(exc_info.value).lower()

    def test_webhook_status_not_active_raises_error(
        self,
        handle_card_webhook_service,
        fake_billing_key_repo,
    ):
        """webhook status가 active가 아니면 오류를 발생시키고 billing key를 저장하지 않는다."""
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="failed",
            signature=VALID_SIGNATURE,
        )

        with pytest.raises(ValueError) as exc_info:
            handle_card_webhook_service.execute(command)

        assert "status" in str(exc_info.value).lower()
        assert fake_billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID) is None

    def test_invalid_card_last_four_format_raises_error(
        self,
        handle_card_webhook_service,
        fake_billing_key_repo,
    ):
        """card_last_four가 4자리 숫자가 아니면 오류를 발생시킨다."""
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=INVALID_CARD_LAST_FOUR_NON_NUMERIC,
            status="active",
            signature=VALID_SIGNATURE,
        )

        with pytest.raises(ValueError) as exc_info:
            handle_card_webhook_service.execute(command)

        assert "card_last_four" in str(exc_info.value).lower()
        assert fake_billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID) is None

    def test_vehicle_not_found_raises_error(
        self,
        fake_card_order_store,
        fake_billing_key_repo,
        fake_signature_verifier,
    ):
        """차량이 DB에 없으면 오류를 발생시키고 billing key를 저장하지 않는다."""
        repo_without_vehicle = FakeVehicleRepository(existing_car_ids=[])
        service = HandleCardWebhookService(
            card_order_store=fake_card_order_store,
            billing_key_repository=fake_billing_key_repo,
            vehicle_repository=repo_without_vehicle,
            signature_verifier=fake_signature_verifier,
        )
        command = HandleCardWebhookCommand(
            order_id=VALID_ORDER_ID,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=VALID_SIGNATURE,
        )

        with pytest.raises(ValueError) as exc_info:
            service.execute(command)

        assert "vehicle" in str(exc_info.value).lower()
        assert fake_billing_key_repo.find_by_car_id(car_id=VALID_CAR_ID) is None
