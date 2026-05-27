"""
카드 등록 / Billing Key 유스케이스 단위 테스트
UC-CARD-001: 카드 등록 order 생성
"""

import pytest

from app.application.card.create_card_order import (
    CreateCardOrderCommand,
    CreateCardOrderService,
)


# ──────────────────────────────────────────────
# 테스트 상수
# ──────────────────────────────────────────────

VALID_USER_ID = "user-001"
VALID_CAR_ID = "car-001"
VALID_PLATE = "12가3456"
VALID_BANK_NAME = "신한은행"
VALID_ORDER_ID = "order-abc-001"
VALID_PG_URL = "https://mock-pg.test/card-register?order_id=order-abc-001"

INVALID_PLATE_FORMAT = "INVALID_PLATE"

OTHER_CAR_ID = "car-999"


# ──────────────────────────────────────────────
# Fake 클래스
# ──────────────────────────────────────────────

class FakeVehicleRepository:
    def __init__(self, existing_car_ids: list[str] | None = None):
        self._existing_car_ids: set[str] = set(existing_car_ids if existing_car_ids is not None else [VALID_CAR_ID])
        self.updated_plates: dict[str, str] = {}

    def exists(self, *, user_id: str, car_id: str) -> bool:
        return car_id in self._existing_car_ids

    def update_plate(self, *, car_id: str, plate: str) -> None:
        self.updated_plates[car_id] = plate


class FakeMolitClient:
    def __init__(self, *, should_pass: bool = True):
        self._should_pass = should_pass
        self.verify_calls: list[dict] = []

    def verify_owner(self, *, plate: str, user_id: str, car_id: str) -> bool:
        self.verify_calls.append({"plate": plate, "user_id": user_id, "car_id": car_id})
        return self._should_pass


class FakeCardOrderStore:
    def __init__(self):
        self.pending_orders: dict[str, dict] = {}

    def save_pending(
        self, *, order_id: str, user_id: str, car_id: str, ttl_seconds: int
    ) -> None:
        self.pending_orders[order_id] = {
            "status": "pending",
            "user_id": user_id,
            "car_id": car_id,
            "ttl_seconds": ttl_seconds,
        }


class FakePgClient:
    def __init__(self, *, pg_url: str = VALID_PG_URL, should_fail: bool = False):
        self._pg_url = pg_url
        self._should_fail = should_fail
        self.create_calls: list[dict] = []

    def create_card_registration_url(self, *, order_id: str) -> str:
        self.create_calls.append({"order_id": order_id})
        if self._should_fail:
            raise RuntimeError("PG URL 생성 실패")
        return self._pg_url


class FakeOrderIdGenerator:
    def __init__(self, *, order_id: str = VALID_ORDER_ID):
        self._order_id = order_id

    def generate(self) -> str:
        return self._order_id


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def fake_vehicle_repo():
    return FakeVehicleRepository()


@pytest.fixture
def fake_molit_client():
    return FakeMolitClient(should_pass=True)


@pytest.fixture
def fake_card_order_store():
    return FakeCardOrderStore()


@pytest.fixture
def fake_pg_client():
    return FakePgClient()


@pytest.fixture
def fake_order_id_generator():
    return FakeOrderIdGenerator()


@pytest.fixture
def create_card_order_service(
    fake_vehicle_repo,
    fake_molit_client,
    fake_card_order_store,
    fake_pg_client,
    fake_order_id_generator,
):
    return CreateCardOrderService(
        vehicle_repository=fake_vehicle_repo,
        molit_client=fake_molit_client,
        card_order_store=fake_card_order_store,
        pg_client=fake_pg_client,
        order_id_generator=fake_order_id_generator,
    )


# ──────────────────────────────────────────────
# 테스트 클래스
# ──────────────────────────────────────────────

class TestCreateCardOrder:
    """UC-CARD-001 - POST /card/order"""

    # ── 성공 케이스 ──

    def test_valid_request_saves_pending_order_to_store(
        self,
        create_card_order_service,
        fake_card_order_store,
    ):
        """유효한 요청이면 order를 pending 상태로 Redis에 저장한다."""
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        create_card_order_service.execute(command)

        assert VALID_ORDER_ID in fake_card_order_store.pending_orders
        assert fake_card_order_store.pending_orders[VALID_ORDER_ID]["status"] == "pending"
        assert fake_card_order_store.pending_orders[VALID_ORDER_ID]["user_id"] == VALID_USER_ID
        assert fake_card_order_store.pending_orders[VALID_ORDER_ID]["car_id"] == VALID_CAR_ID

    def test_valid_request_returns_order_id_and_pg_url(
        self,
        create_card_order_service,
    ):
        """유효한 요청이면 order_id와 pg_url을 반환한다."""
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        result = create_card_order_service.execute(command)

        assert result.order_id == VALID_ORDER_ID
        assert result.pg_url == VALID_PG_URL

    def test_valid_request_calls_molit_owner_verification(
        self,
        create_card_order_service,
        fake_molit_client,
    ):
        """유효한 요청이면 MOLIT 소유자 검증을 호출한다."""
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        create_card_order_service.execute(command)

        assert len(fake_molit_client.verify_calls) == 1
        assert fake_molit_client.verify_calls[0]["plate"] == VALID_PLATE

    def test_valid_request_calls_pg_to_create_url(
        self,
        create_card_order_service,
        fake_pg_client,
    ):
        """유효한 요청이면 PG card registration URL 생성을 호출한다."""
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        create_card_order_service.execute(command)

        assert len(fake_pg_client.create_calls) == 1
        assert fake_pg_client.create_calls[0]["order_id"] == VALID_ORDER_ID

    # ── 실패 케이스 ──
    #
    # [인증 실패 케이스 제외 이유]
    # UC-CARD-001 실패 케이스 중 "인증 실패"는 이 unit test에서 다루지 않는다.
    # 인증(app access token 검증)은 서비스 레이어가 아닌 HTTP 미들웨어/의존성 레이어에서 처리하므로,
    # unit test 대상이 아니다.
    # 인증 실패(401)는 tests/integration/api/test_uc_card_api_001_002_card_order_and_webhook.py
    # 의 API test에서 검증한다.

    def test_agree_terms_false_raises_error(
        self,
        create_card_order_service,
        fake_card_order_store,
    ):
        """약관 미동의면 오류를 발생시키고 order를 저장하지 않는다."""
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=False,
        )

        with pytest.raises(ValueError) as exc_info:
            create_card_order_service.execute(command)

        assert "agree_terms" in str(exc_info.value)
        assert len(fake_card_order_store.pending_orders) == 0

    def test_vehicle_not_found_raises_error(
        self,
        fake_molit_client,
        fake_card_order_store,
        fake_pg_client,
        fake_order_id_generator,
    ):
        """차량이 DB에 없으면 오류를 발생시킨다."""
        repo_without_vehicle = FakeVehicleRepository(existing_car_ids=[])
        service = CreateCardOrderService(
            vehicle_repository=repo_without_vehicle,
            molit_client=fake_molit_client,
            card_order_store=fake_card_order_store,
            pg_client=fake_pg_client,
            order_id_generator=fake_order_id_generator,
        )
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        with pytest.raises(ValueError) as exc_info:
            service.execute(command)

        assert "vehicle" in str(exc_info.value).lower()

    def test_invalid_plate_format_raises_error(
        self,
        create_card_order_service,
        fake_card_order_store,
    ):
        """차량번호 형식이 유효하지 않으면 오류를 발생시킨다."""
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=INVALID_PLATE_FORMAT,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        with pytest.raises(ValueError) as exc_info:
            create_card_order_service.execute(command)

        assert "plate" in str(exc_info.value).lower()
        assert len(fake_card_order_store.pending_orders) == 0

    def test_molit_verification_failure_does_not_create_order(
        self,
        fake_vehicle_repo,
        fake_card_order_store,
        fake_pg_client,
        fake_order_id_generator,
    ):
        """MOLIT 검증 실패 시 order를 생성하지 않는다."""
        molit_client_that_fails = FakeMolitClient(should_pass=False)
        service = CreateCardOrderService(
            vehicle_repository=fake_vehicle_repo,
            molit_client=molit_client_that_fails,
            card_order_store=fake_card_order_store,
            pg_client=fake_pg_client,
            order_id_generator=fake_order_id_generator,
        )
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        with pytest.raises(ValueError):
            service.execute(command)

        assert len(fake_card_order_store.pending_orders) == 0

    def test_pg_url_creation_failure_raises_error(
        self,
        fake_vehicle_repo,
        fake_molit_client,
        fake_card_order_store,
        fake_order_id_generator,
    ):
        """PG URL 생성 실패 시 오류를 발생시킨다."""
        pg_client_that_fails = FakePgClient(should_fail=True)
        service = CreateCardOrderService(
            vehicle_repository=fake_vehicle_repo,
            molit_client=fake_molit_client,
            card_order_store=fake_card_order_store,
            pg_client=pg_client_that_fails,
            order_id_generator=fake_order_id_generator,
        )
        command = CreateCardOrderCommand(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK_NAME,
            agree_terms=True,
        )

        with pytest.raises(RuntimeError):
            service.execute(command)
