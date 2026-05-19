"""
카드 등록 / Billing Key 유즈케이스 단위 테스트
UC-CARD-001: 카드 등록 order 생성
UC-CARD-002: 카드 등록 완료 webhook 처리
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# 공통 상수
# ---------------------------------------------------------------------------

VALID_USER_ID = "user-001"
VALID_CAR_ID = "car-001"
VALID_PLATE = "12가3456"
VALID_BANK = "신한"
VALID_ORDER_ID = str(uuid.uuid4())
VALID_BILLING_KEY = "bk-test-abc123"
VALID_CARD_LAST_FOUR = "1234"
WEBHOOK_SECRET = "test-webhook-secret"


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------


def make_hmac_signature(order_id: str, billing_key: str, secret: str = WEBHOOK_SECRET) -> str:
    """HMAC-SHA256 signature 생성"""
    payload = f"{order_id}:{billing_key}"
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_molit():
    molit = AsyncMock()
    molit.verify_owner = AsyncMock(return_value=True)
    return molit


@pytest.fixture
def mock_vehicle_repo():
    repo = AsyncMock()
    repo.find_by_car_id = AsyncMock(return_value=None)
    repo.update_plate = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_billing_key_repo():
    repo = AsyncMock()
    repo.upsert = AsyncMock(return_value=True)
    repo.find_by_car_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_card_service(mock_redis, mock_molit, mock_vehicle_repo):
    """
    실제 CardService 구현체 대신, 이 테스트에서 검증하는 시나리오 계약을
    반영하는 인터페이스 모킹.
    실제 구현 시 아래 FakeCardService를 실제 서비스로 교체한다.
    """
    return FakeCardService(
        redis=mock_redis,
        molit=mock_molit,
        vehicle_repo=mock_vehicle_repo,
    )


@pytest.fixture
def mock_webhook_service(mock_redis, mock_billing_key_repo):
    return FakeWebhookService(
        redis=mock_redis,
        billing_key_repo=mock_billing_key_repo,
        secret=WEBHOOK_SECRET,
    )


# ---------------------------------------------------------------------------
# Fake 서비스 (테스트용 인터페이스 구현체)
# 실제 서비스 레이어가 완성되면 이 클래스를 제거하고 실제 서비스로 교체한다.
# ---------------------------------------------------------------------------

import re


def _normalize_plate(plate: str) -> str:
    """차량번호 정규화: 공백·하이픈 제거"""
    normalized = re.sub(r"[\s\-]", "", plate)
    # 한국 차량번호 형식 검증: 숫자2 + 한글1 + 숫자4
    if not re.fullmatch(r"\d{2,3}[가-힣]\d{4}", normalized):
        raise HTTPException(status_code=400, detail="차량번호 형식이 올바르지 않습니다.")
    return normalized


class FakeCardService:
    def __init__(self, redis, molit, vehicle_repo):
        self.redis = redis
        self.molit = molit
        self.vehicle_repo = vehicle_repo

    async def create_order(
        self,
        *,
        user_id: str | None,
        car_id: str | None,
        plate: str,
        bank_name: str,
        agree_terms: bool,
    ) -> dict:
        # 인증 검사
        if not user_id or not car_id:
            raise HTTPException(status_code=401, detail="인증 실패")

        # 약관 동의 검사
        if not agree_terms:
            raise HTTPException(status_code=400, detail="약관 동의가 필요합니다 (terms)")

        # 차량 존재 여부
        vehicle = await self.vehicle_repo.find_by_car_id(car_id)
        if vehicle is None:
            raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다.")

        # 차량번호 정규화 및 형식 검증
        normalized_plate = _normalize_plate(plate)
        # 항상 정규화 결과를 DB에 반영한다 (같더라도 명시적 upsert)
        await self.vehicle_repo.update_plate(car_id, normalized_plate)

        # MOLIT 소유자 검증
        is_valid = await self.molit.verify_owner(
            plate=normalized_plate,
            user_id=user_id,
        )
        if not is_valid:
            raise HTTPException(status_code=422, detail="MOLIT 소유자 검증 실패")

        # Order 생성 및 Redis 저장
        order_id = str(uuid.uuid4())
        redis_key = f"mock_pg_card_register:{order_id}"
        redis_value = json.dumps(
            {"status": "pending", "car_id": car_id, "user_id": user_id}
        )
        await self.redis.set(redis_key, redis_value)

        # Mock PG URL 생성
        pg_url = f"https://mock-pg.example.com/register?order_id={order_id}"

        return {"order_id": order_id, "pg_url": pg_url}


class FakeWebhookService:
    def __init__(self, redis, billing_key_repo, secret: str):
        self.redis = redis
        self.billing_key_repo = billing_key_repo
        self.secret = secret

    def _verify_signature(self, order_id: str, billing_key: str, signature: str) -> bool:
        expected = hmac.new(
            self.secret.encode(),
            f"{order_id}:{billing_key}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def handle_webhook(
        self,
        *,
        order_id: str,
        billing_key: str,
        card_last_four: str,
        status: str,
        signature: str,
    ) -> dict:
        # Signature 검증
        if not self._verify_signature(order_id, billing_key, signature):
            raise HTTPException(status_code=401, detail="signature 불일치")

        # card_last_four 형식 검증
        if not re.fullmatch(r"\d{4}", card_last_four):
            raise HTTPException(status_code=400, detail="card_last_four 형식 오류")

        # Redis order 조회
        redis_key = f"mock_pg_card_register:{order_id}"
        raw = await self.redis.get(redis_key)
        if raw is None:
            raise HTTPException(status_code=400, detail="order가 없거나 만료됨")

        order_data = json.loads(raw)
        # complete 상태면 멱등성 처리
        if order_data.get("status") == "complete":
            return {"status": "ok"}

        # webhook status 검증
        if status != "active":
            raise HTTPException(status_code=400, detail="webhook status가 active가 아님")

        car_id = order_data["car_id"]

        # vehicle_billing_keys upsert
        await self.billing_key_repo.upsert(
            car_id=car_id,
            billing_key=billing_key,
            card_last_four=card_last_four,
            status="active",
        )

        # Redis order complete 처리
        complete_value = json.dumps({**order_data, "status": "complete"})
        await self.redis.set(redis_key, complete_value)

        return {"status": "ok"}


# ===========================================================================
# UC-CARD-001: 카드 등록 order 생성
# ===========================================================================


class TestCreateCardOrder:
    """UC-CARD-001 - POST /card/order"""

    # TC-001-01: 정상 요청 → Redis 저장 + pg_url 반환
    @pytest.mark.asyncio
    async def test_valid_request_stores_order_and_returns_pg_url(
        self,
        mock_card_service,
        mock_redis,
        mock_molit,
        mock_vehicle_repo,
    ):
        """유효한 요청이면 order를 Redis에 pending으로 저장하고 pg_url을 반환한다."""
        mock_vehicle_repo.find_by_car_id.return_value = {
            "car_id": VALID_CAR_ID,
            "user_id": VALID_USER_ID,
            "plate": VALID_PLATE,
        }
        mock_molit.verify_owner.return_value = True

        result = await mock_card_service.create_order(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            bank_name=VALID_BANK,
            agree_terms=True,
        )

        assert "order_id" in result
        assert "pg_url" in result
        assert result["pg_url"].startswith("https://")

        # Redis에 pending 상태로 저장됐는지 확인
        order_id = result["order_id"]
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args[0]
        assert call_args[0] == f"mock_pg_card_register:{order_id}"
        assert json.loads(call_args[1])["status"] == "pending"

    # TC-001-02: 약관 미동의 → 400 반환
    @pytest.mark.asyncio
    async def test_disagree_terms_returns_400(self, mock_card_service):
        """agree_terms가 False면 400을 반환하고 order를 생성하지 않는다."""
        with pytest.raises(HTTPException) as exc_info:
            await mock_card_service.create_order(
                user_id=VALID_USER_ID,
                car_id=VALID_CAR_ID,
                plate=VALID_PLATE,
                bank_name=VALID_BANK,
                agree_terms=False,
            )

        assert exc_info.value.status_code == 400
        assert "terms" in exc_info.value.detail.lower() or "약관" in exc_info.value.detail

    # TC-001-03: MOLIT 검증 실패 → order 미생성
    @pytest.mark.asyncio
    async def test_molit_failure_does_not_create_order(
        self,
        mock_card_service,
        mock_redis,
        mock_molit,
        mock_vehicle_repo,
    ):
        """MOLIT 소유자 검증이 실패하면 order를 Redis에 저장하지 않는다."""
        mock_vehicle_repo.find_by_car_id.return_value = {
            "car_id": VALID_CAR_ID,
            "user_id": VALID_USER_ID,
            "plate": VALID_PLATE,
        }
        mock_molit.verify_owner.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await mock_card_service.create_order(
                user_id=VALID_USER_ID,
                car_id=VALID_CAR_ID,
                plate=VALID_PLATE,
                bank_name=VALID_BANK,
                agree_terms=True,
            )

        assert exc_info.value.status_code in (400, 422)
        mock_redis.set.assert_not_called()

    # TC-001-04: 차량 없음 → 404 반환
    @pytest.mark.asyncio
    async def test_vehicle_not_found_returns_404(
        self,
        mock_card_service,
        mock_vehicle_repo,
    ):
        """토큰의 car_id에 해당하는 차량이 DB에 없으면 404를 반환한다."""
        mock_vehicle_repo.find_by_car_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await mock_card_service.create_order(
                user_id=VALID_USER_ID,
                car_id="nonexistent-car",
                plate=VALID_PLATE,
                bank_name=VALID_BANK,
                agree_terms=True,
            )

        assert exc_info.value.status_code == 404

    # TC-001-05: 잘못된 차량번호 형식 → 400 반환
    @pytest.mark.asyncio
    async def test_invalid_plate_format_returns_400(
        self, mock_card_service, mock_vehicle_repo
    ):
        """차량번호 형식이 유효하지 않으면 400을 반환한다."""
        mock_vehicle_repo.find_by_car_id.return_value = {
            "car_id": VALID_CAR_ID,
            "user_id": VALID_USER_ID,
            "plate": VALID_PLATE,
        }

        with pytest.raises(HTTPException) as exc_info:
            await mock_card_service.create_order(
                user_id=VALID_USER_ID,
                car_id=VALID_CAR_ID,
                plate="INVALID##PLATE",
                bank_name=VALID_BANK,
                agree_terms=True,
            )

        assert exc_info.value.status_code == 400

    # TC-001-06: 인증 토큰 없음 → 401 반환
    @pytest.mark.asyncio
    async def test_missing_auth_token_returns_401(self, mock_card_service):
        """app access token이 없으면 401을 반환한다."""
        with pytest.raises(HTTPException) as exc_info:
            await mock_card_service.create_order(
                user_id=None,
                car_id=None,
                plate=VALID_PLATE,
                bank_name=VALID_BANK,
                agree_terms=True,
            )

        assert exc_info.value.status_code == 401

    # TC-001-07: 차량번호 정규화 후 DB 업데이트
    @pytest.mark.asyncio
    async def test_plate_normalization_updates_db(
        self,
        mock_card_service,
        mock_redis,
        mock_molit,
        mock_vehicle_repo,
    ):
        """차량번호 정규화 후 DB 값과 다르면 vehicles.plate를 업데이트한다."""
        # DB에는 하이픈 포함 비정규화 값이 저장돼 있다
        mock_vehicle_repo.find_by_car_id.return_value = {
            "car_id": VALID_CAR_ID,
            "user_id": VALID_USER_ID,
            "plate": "12-가-3456",
        }
        mock_molit.verify_owner.return_value = True

        await mock_card_service.create_order(
            user_id=VALID_USER_ID,
            car_id=VALID_CAR_ID,
            plate="12-가-3456",
            bank_name=VALID_BANK,
            agree_terms=True,
        )

        # 정규화된 값으로 DB 업데이트 호출 확인
        mock_vehicle_repo.update_plate.assert_called_once_with(VALID_CAR_ID, "12가3456")


# ===========================================================================
# UC-CARD-002: 카드 등록 완료 webhook 처리
# ===========================================================================


class TestCardWebhook:
    """UC-CARD-002 - POST /card/webhook"""

    # TC-002-01: 정상 webhook → active billing key 저장
    @pytest.mark.asyncio
    async def test_valid_webhook_saves_active_billing_key(
        self,
        mock_webhook_service,
        mock_redis,
        mock_billing_key_repo,
    ):
        """정상 webhook이면 vehicle_billing_keys에 active billing key를 저장한다."""
        order_id = VALID_ORDER_ID
        signature = make_hmac_signature(order_id, VALID_BILLING_KEY)
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID, "user_id": VALID_USER_ID}
        )

        result = await mock_webhook_service.handle_webhook(
            order_id=order_id,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=signature,
        )

        assert result == {"status": "ok"}
        mock_billing_key_repo.upsert.assert_called_once()
        kwargs = mock_billing_key_repo.upsert.call_args[1]
        assert kwargs["car_id"] == VALID_CAR_ID
        assert kwargs["billing_key"] == VALID_BILLING_KEY
        assert kwargs["status"] == "active"
        assert kwargs["card_last_four"] == VALID_CARD_LAST_FOUR

    # TC-002-02: 중복 webhook → 멱등성 보장
    @pytest.mark.asyncio
    async def test_duplicate_webhook_is_idempotent(
        self,
        mock_webhook_service,
        mock_redis,
        mock_billing_key_repo,
    ):
        """같은 webhook이 두 번 와도 결과가 깨지지 않는다 (멱등성)."""
        order_id = VALID_ORDER_ID
        signature = make_hmac_signature(order_id, VALID_BILLING_KEY)

        # 첫 번째 호출 (pending)
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID, "user_id": VALID_USER_ID}
        )
        first = await mock_webhook_service.handle_webhook(
            order_id=order_id,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=signature,
        )

        # 두 번째 호출 (complete 상태로 변경됨)
        mock_redis.get.return_value = json.dumps(
            {"status": "complete", "car_id": VALID_CAR_ID, "user_id": VALID_USER_ID}
        )
        second = await mock_webhook_service.handle_webhook(
            order_id=order_id,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=signature,
        )

        assert first == {"status": "ok"}
        assert second == {"status": "ok"}
        # 두 번째에는 upsert를 다시 호출하지 않아야 한다
        assert mock_billing_key_repo.upsert.call_count == 1

    # TC-002-03: order 없음 → 400 반환
    @pytest.mark.asyncio
    async def test_missing_order_returns_400(self, mock_webhook_service, mock_redis):
        """Redis에 해당 order가 없으면 400을 반환한다."""
        mock_redis.get.return_value = None
        order_id = VALID_ORDER_ID
        signature = make_hmac_signature(order_id, VALID_BILLING_KEY)

        with pytest.raises(HTTPException) as exc_info:
            await mock_webhook_service.handle_webhook(
                order_id=order_id,
                billing_key=VALID_BILLING_KEY,
                card_last_four=VALID_CARD_LAST_FOUR,
                status="active",
                signature=signature,
            )

        assert exc_info.value.status_code == 400

    # TC-002-04: signature 불일치 → 400 또는 401 반환
    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401_or_400(
        self, mock_webhook_service, mock_redis
    ):
        """signature가 틀리면 401 또는 400을 반환한다."""
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID}
        )

        with pytest.raises(HTTPException) as exc_info:
            await mock_webhook_service.handle_webhook(
                order_id=VALID_ORDER_ID,
                billing_key=VALID_BILLING_KEY,
                card_last_four=VALID_CARD_LAST_FOUR,
                status="active",
                signature="tampered-invalid-signature",
            )

        assert exc_info.value.status_code in (400, 401)

    # TC-002-05: webhook status != active → billing key 저장 안 함
    @pytest.mark.asyncio
    async def test_non_active_status_does_not_save_billing_key(
        self,
        mock_webhook_service,
        mock_redis,
        mock_billing_key_repo,
    ):
        """webhook status가 'active'가 아니면 billing key를 저장하지 않는다."""
        order_id = VALID_ORDER_ID
        signature = make_hmac_signature(order_id, VALID_BILLING_KEY)
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID}
        )

        with pytest.raises(HTTPException) as exc_info:
            await mock_webhook_service.handle_webhook(
                order_id=order_id,
                billing_key=VALID_BILLING_KEY,
                card_last_four=VALID_CARD_LAST_FOUR,
                status="failed",
                signature=signature,
            )

        assert exc_info.value.status_code in (400, 422)
        mock_billing_key_repo.upsert.assert_not_called()

    # TC-002-06: card_last_four 형식 오류 → 400 반환
    @pytest.mark.asyncio
    async def test_invalid_card_last_four_returns_400(
        self, mock_webhook_service, mock_redis
    ):
        """card_last_four가 4자리 숫자가 아니면 400을 반환한다."""
        order_id = VALID_ORDER_ID
        signature = make_hmac_signature(order_id, VALID_BILLING_KEY)
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID}
        )

        with pytest.raises(HTTPException) as exc_info:
            await mock_webhook_service.handle_webhook(
                order_id=order_id,
                billing_key=VALID_BILLING_KEY,
                card_last_four="12AB",
                status="active",
                signature=signature,
            )

        assert exc_info.value.status_code == 400

    # TC-002-07: 기존 billing key → 새 값으로 교체 (upsert)
    @pytest.mark.asyncio
    async def test_existing_billing_key_is_replaced(
        self,
        mock_webhook_service,
        mock_redis,
        mock_billing_key_repo,
    ):
        """기존 billing key가 있으면 새 값으로 교체(upsert)한다."""
        order_id = VALID_ORDER_ID
        new_billing_key = "bk-new-xyz789"
        signature = make_hmac_signature(order_id, new_billing_key)
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID, "user_id": VALID_USER_ID}
        )
        mock_billing_key_repo.find_by_car_id.return_value = {
            "car_id": VALID_CAR_ID,
            "billing_key": "bk-old-aaa111",
            "status": "active",
        }

        result = await mock_webhook_service.handle_webhook(
            order_id=order_id,
            billing_key=new_billing_key,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=signature,
        )

        assert result == {"status": "ok"}
        upsert_kwargs = mock_billing_key_repo.upsert.call_args[1]
        assert upsert_kwargs["billing_key"] == new_billing_key

    # TC-002-08: webhook 처리 후 Redis order 정리
    @pytest.mark.asyncio
    async def test_redis_order_is_cleaned_up_after_webhook(
        self,
        mock_webhook_service,
        mock_redis,
        mock_billing_key_repo,
    ):
        """webhook 처리 후 Redis order를 삭제하거나 complete 상태로 변경한다."""
        order_id = VALID_ORDER_ID
        signature = make_hmac_signature(order_id, VALID_BILLING_KEY)
        mock_redis.get.return_value = json.dumps(
            {"status": "pending", "car_id": VALID_CAR_ID, "user_id": VALID_USER_ID}
        )

        await mock_webhook_service.handle_webhook(
            order_id=order_id,
            billing_key=VALID_BILLING_KEY,
            card_last_four=VALID_CARD_LAST_FOUR,
            status="active",
            signature=signature,
        )

        deleted = mock_redis.delete.called
        set_complete = mock_redis.set.called and "complete" in str(mock_redis.set.call_args)
        assert deleted or set_complete, "Redis order가 삭제되거나 complete로 변경돼야 합니다."
