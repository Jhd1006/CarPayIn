"""
UC-CARD-002: 카드 등록 완료 webhook 처리
"""

import re
from dataclasses import dataclass
from typing import Protocol


# ──────────────────────────────────────────────
# Command / Result
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class HandleCardWebhookCommand:
    order_id: str
    billing_key: str
    card_last_four: str
    status: str
    signature: str
    signature_timestamp: str = "0"
    raw_body: bytes = b"{}"


@dataclass(frozen=True)
class HandleCardWebhookResult:
    status: str = "ok"


# ──────────────────────────────────────────────
# Protocol (인터페이스 정의)
# 테스트의 Fake 클래스들이 구현해야 할 메서드를 명시한다.
# ──────────────────────────────────────────────

class CardOrderStore(Protocol):
    def get_pending(self, *, order_id: str) -> dict | None:
        ...

    def get_order(self, *, order_id: str) -> dict | None:
        """상태에 관계없이 order를 조회한다 (멱등성 확인용)."""
        ...

    def mark_complete(self, *, order_id: str) -> None:
        ...

    def delete(self, *, order_id: str) -> None:
        ...


class BillingKeyRepository(Protocol):
    def upsert(self, *, car_id: str, billing_key: str, card_last_four: str) -> None:
        ...

    def find_by_car_id(self, *, car_id: str) -> dict | None:
        ...


class VehicleRepository(Protocol):
    def exists_by_car_id(self, *, car_id: str) -> bool:
        ...


class SignatureVerifier(Protocol):
    def verify(self, *, timestamp: str, signature: str, body: bytes) -> bool:
        ...


# ──────────────────────────────────────────────
# card_last_four 유효성 검사
# ──────────────────────────────────────────────

_CARD_LAST_FOUR_PATTERN = re.compile(r"^\d{4}$")


def _validate_card_last_four(card_last_four: str) -> None:
    """card_last_four가 4자리 숫자가 아니면 ValueError를 발생시킨다."""
    if not _CARD_LAST_FOUR_PATTERN.match(card_last_four):
        raise ValueError(f"card_last_four는 4자리 숫자여야 합니다: {card_last_four}")


# ──────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────

class HandleCardWebhookService:
    def __init__(
        self,
        *,
        card_order_store: CardOrderStore,
        billing_key_repository: BillingKeyRepository,
        vehicle_repository: VehicleRepository,
        signature_verifier: SignatureVerifier,
    ) -> None:
        self._card_order_store = card_order_store
        self._billing_key_repository = billing_key_repository
        self._vehicle_repository = vehicle_repository
        self._signature_verifier = signature_verifier

    def execute(self, command: HandleCardWebhookCommand) -> HandleCardWebhookResult:
        # 1. signature 검증
        if not self._signature_verifier.verify(
            timestamp=command.signature_timestamp,
            signature=command.signature,
            body=command.raw_body,
        ):
            raise ValueError("invalid_signature")

        # 2. card_last_four 형식 검증
        _validate_card_last_four(command.card_last_four)

        # 3. webhook status 확인
        if command.status != "active":
            raise ValueError(f"webhook status가 active가 아닙니다: {command.status}")

        # 4. Redis에서 pending order 조회
        order = self._card_order_store.get_pending(order_id=command.order_id)
        if order is None:
            # 이미 처리된 order면 멱등성 보장으로 ok 반환
            existing = self._card_order_store.get_order(order_id=command.order_id)
            if existing is not None:
                return HandleCardWebhookResult(status="ok")
            raise ValueError(f"order를 찾을 수 없거나 만료되었습니다. order_id={command.order_id}")

        # 5. 차량 존재 여부 재확인
        car_id = order["car_id"]
        if not self._vehicle_repository.exists_by_car_id(car_id=car_id):
            raise ValueError(f"vehicle을 찾을 수 없습니다. car_id={car_id}")

        # 6. vehicle_billing_keys upsert (최초 등록 or 카드 변경)
        self._billing_key_repository.upsert(
            car_id=car_id,
            billing_key=command.billing_key,
            card_last_four=command.card_last_four,
        )

        # 7. Redis order 완료 처리
        self._card_order_store.mark_complete(order_id=command.order_id)

        return HandleCardWebhookResult(status="ok")
