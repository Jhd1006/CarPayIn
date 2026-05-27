"""
UC-CARD-001: 카드 등록 order 생성
"""

import re
from dataclasses import dataclass
from typing import Protocol


# ──────────────────────────────────────────────
# Command / Result
# ──────────────────────────────────────────────

@dataclass(frozen=True)
class CreateCardOrderCommand:
    user_id: str
    car_id: str
    plate: str
    bank_name: str
    agree_terms: bool


@dataclass(frozen=True)
class CreateCardOrderResult:
    order_id: str
    pg_url: str


# ──────────────────────────────────────────────
# Protocol (인터페이스 정의)
# 테스트의 Fake 클래스들이 구현해야 할 메서드를 명시한다.
# ──────────────────────────────────────────────

class VehicleRepository(Protocol):
    def exists(self, *, user_id: str, car_id: str) -> bool:
        ...

    def update_plate(self, *, car_id: str, plate: str) -> None:
        ...


class MolitClient(Protocol):
    def verify_owner(self, *, plate: str, user_id: str, car_id: str) -> bool:
        ...


CARD_ORDER_TTL_SECONDS = 30 * 60


class CardOrderStore(Protocol):
    def save_pending(
        self, *, order_id: str, user_id: str, car_id: str, ttl_seconds: int
    ) -> None:
        ...


class PgClient(Protocol):
    def create_card_registration_url(self, *, order_id: str) -> str:
        ...


class OrderIdGenerator(Protocol):
    def generate(self) -> str:
        ...


# ──────────────────────────────────────────────
# 차량번호 정규화 및 유효성 검사
# ──────────────────────────────────────────────

# 유효한 차량번호 형식 예: 12가3456, 123가4567
_PLATE_PATTERN = re.compile(r"^\d{2,3}[가-힣]\d{4}$")


def _normalize_plate(plate: str) -> str:
    """차량번호에서 공백을 제거하고 정규화한다."""
    return plate.replace(" ", "").strip()


def _validate_plate(plate: str) -> None:
    """차량번호 형식이 유효하지 않으면 ValueError를 발생시킨다."""
    if not _PLATE_PATTERN.match(plate):
        raise ValueError(f"plate 형식이 유효하지 않습니다: {plate}")


# ──────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────

class CreateCardOrderService:
    def __init__(
        self,
        *,
        vehicle_repository: VehicleRepository,
        molit_client: MolitClient,
        card_order_store: CardOrderStore,
        pg_client: PgClient,
        order_id_generator: OrderIdGenerator,
    ) -> None:
        self._vehicle_repository = vehicle_repository
        self._molit_client = molit_client
        self._card_order_store = card_order_store
        self._pg_client = pg_client
        self._order_id_generator = order_id_generator

    def execute(self, command: CreateCardOrderCommand) -> CreateCardOrderResult:
        # 1. 약관 동의 확인
        if not command.agree_terms:
            raise ValueError("agree_terms가 true여야 합니다.")

        # 2. 차량 존재 여부 확인
        if not self._vehicle_repository.exists(
            user_id=command.user_id,
            car_id=command.car_id,
        ):
            raise ValueError(f"vehicle을 찾을 수 없습니다. car_id={command.car_id}")

        # 3. 차량번호 정규화 및 유효성 검사
        normalized_plate = _normalize_plate(command.plate)
        _validate_plate(normalized_plate)

        # 4. MOLIT 소유자 검증
        is_verified = self._molit_client.verify_owner(
            plate=normalized_plate,
            user_id=command.user_id,
            car_id=command.car_id,
        )
        if not is_verified:
            raise ValueError("MOLIT 소유자 검증에 실패했습니다.")

        # 5. order_id 생성
        order_id = self._order_id_generator.generate()

        # 6. Redis에 카드 등록 세션 저장
        self._card_order_store.save_pending(
            order_id=order_id,
            user_id=command.user_id,
            car_id=command.car_id,
            ttl_seconds=CARD_ORDER_TTL_SECONDS,
        )

        # 7. PG 카드 등록 URL 생성
        pg_url = self._pg_client.create_card_registration_url(order_id=order_id)

        # 8. 결과 반환
        return CreateCardOrderResult(
            order_id=order_id,
            pg_url=pg_url,
        )
