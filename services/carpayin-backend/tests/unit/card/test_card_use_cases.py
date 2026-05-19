"""
UC-CARD-001  카드 등록 order 생성     POST /card/order
UC-CARD-002  카드 등록 완료 webhook 처리  POST /webhook/card

외부 의존성 처리:
  - DB    : 테스트별 독립된 임시 SQLite 파일 (database.DB_PATH monkeypatch)
  - MOLIT : main._molit_owner_check 를 fixture 로 대체
  - MQTT  : mqtt_service.start / publish 를 no-op fixture 로 대체

참고:
  비즈니스 로직이 라우터에 인라인되어 있어 TestClient 를 사용하는
  API 통합 테스트로 작성한다. HTTP status code 검증은 이 레이어에서 수행한다.
  실제 구현체: services/carpayin-server/main.py
"""

import hashlib
import hmac as hmac_lib
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

# ── 공통 상수 ────────────────────────────────────────────────────────────────
VALID_CAR_ID      = "car-test-001"
VALID_PLATE       = "12가3456"
VALID_BANK_NAME   = "신한카드"
ACCESS_TOKEN      = "test-access-token-abc"
HMAC_SECRET       = "dev-only-change-me"

ORDER_ID          = "testorder0000001a"
PAYMENT_METHOD_ID = "pm-test-0001"
CUSTOMER_KEY      = "ckey-test-0001"
CARD_BRAND        = "신한카드"
LAST_FOUR         = "1234"

AUTH_HEADER       = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


# ── HMAC 계산 헬퍼 ────────────────────────────────────────────────────────────
def _make_hmac(
    order_id: str,
    customer_key: str,
    payment_method_id: str,
    card_brand: str,
    last_four: str,
    secret: str = HMAC_SECRET,
) -> str:
    """main.py 의 webhook HMAC 생성 로직과 동일하게 계산한다."""
    payload = {
        "card_brand": card_brand,
        "customer_key": customer_key,
        "last_four": last_four,
        "order_id": order_id,
        "payment_method_id": payment_method_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac_lib.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def no_mqtt(monkeypatch):
    """MQTT 브로커 연결을 no-op 으로 대체해 테스트 환경에서 연결 오류를 방지한다."""
    monkeypatch.setattr("mqtt_service.start", lambda: None)
    monkeypatch.setattr("mqtt_service.client", None, raising=False)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """각 테스트별 독립된 SQLite DB 를 생성하고 스키마를 초기화한다."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("database.DB_PATH", db_file)
    import database
    database.init_db()
    return db_file


@pytest.fixture
def seeded_db(test_db):
    """유효한 차량 및 만료되지 않은 access token 을 DB 에 삽입한다."""
    import database
    expires = (datetime.now() + timedelta(hours=24)).isoformat()
    with database.get_conn() as con:
        con.execute(
            "INSERT INTO vehicles (car_id, plate) VALUES (?, ?)",
            (VALID_CAR_ID, ""),
        )
        con.execute(
            "INSERT INTO tokens (access_token, car_id, hyundai_user_id, expires_at)"
            " VALUES (?, ?, ?, ?)",
            (ACCESS_TOKEN, VALID_CAR_ID, "", expires),
        )
    return test_db


@pytest.fixture
def molit_pass(monkeypatch):
    """MOLIT 소유자 검증이 항상 통과하도록 대체한다."""
    def _pass(plate, car_id, hyundai_user_id="", owner_name=""):
        return {
            "matched": True,
            "message": "Mock PASS",
            "checked_at": datetime.now().isoformat(),
            "plate": plate,
            "car_id": car_id,
            "owner_user_id": hyundai_user_id,
            "owner_name": owner_name,
            "registry_hit": True,
        }
    monkeypatch.setattr("main._molit_owner_check", _pass)


@pytest.fixture
def molit_fail(monkeypatch):
    """MOLIT 소유자 검증이 항상 실패하도록 대체한다."""
    def _fail(plate, car_id, hyundai_user_id="", owner_name=""):
        return {
            "matched": False,
            "message": "소유주 정보 불일치 (Mock)",
            "checked_at": datetime.now().isoformat(),
            "plate": plate,
            "car_id": car_id,
            "owner_user_id": hyundai_user_id,
            "owner_name": owner_name,
            "registry_hit": False,
        }
    monkeypatch.setattr("main._molit_owner_check", _fail)


@pytest.fixture
def client(no_mqtt, test_db):
    """
    실제 main.app 을 사용하는 TestClient.
    test_db 에서 DB 경로를 먼저 패치한 뒤 TestClient lifespan 을 시작해
    init_db() 가 테스트 DB 에 적용되도록 한다.
    """
    from main import app
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════════
# UC-CARD-001 · POST /card/order
# ═══════════════════════════════════════════════════════════════════════════════

class TestCardOrderCreate:
    """UC-CARD-001: 카드 등록 order 생성."""

    # ── 성공 케이스 ──────────────────────────────────────────────────────────

    def test_유효한요청_order_id와_pg_url반환(self, client, seeded_db, molit_pass):
        # Given: 유효한 토큰, 등록된 차량, 약관 동의, 유효한 번호판
        payload = {"plate": VALID_PLATE, "bank_name": VALID_BANK_NAME, "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 200
        body = resp.json()
        assert "order_id" in body
        assert "pg_url" in body
        assert body["plate"] == VALID_PLATE

    def test_유효한요청_card_orders_DB에_저장됨(self, client, seeded_db, molit_pass):
        # Given
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then: 반환된 order_id 로 card_orders 에 car_id 가 저장되어야 한다
        import database
        order_id = resp.json()["order_id"]
        with database.get_conn() as con:
            row = con.execute(
                "SELECT car_id FROM card_orders WHERE order_id=?", (order_id,)
            ).fetchone()
        assert row is not None
        assert row["car_id"] == VALID_CAR_ID

    def test_bank_name_제공시_pg_url에_card_brand_포함(self, client, seeded_db, molit_pass):
        # Given: bank_name 제공
        payload = {"plate": VALID_PLATE, "bank_name": VALID_BANK_NAME, "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then: pg_url 에 card_brand 파라미터가 포함됨
        assert resp.status_code == 200
        assert "card_brand" in resp.json()["pg_url"]

    def test_번호판_공백포함시_정규화후_성공(self, client, seeded_db, molit_pass):
        # Given: 공백이 포함된 번호판 입력
        payload = {"plate": "12 가 3456", "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then: 정규화 후 유효한 번호판으로 처리됨
        assert resp.status_code == 200
        assert resp.json()["plate"] == "12가3456"

    # ── 실패 케이스 ──────────────────────────────────────────────────────────

    def test_약관미동의_400반환(self, client, seeded_db, molit_pass):
        # Given: agree_terms=False
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": False}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 400

    def test_약관미동의_card_orders_저장안됨(self, client, seeded_db, molit_pass):
        # Given
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": False}

        # When
        client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then: 거부 후 card_orders 에 데이터가 없어야 한다
        import database
        with database.get_conn() as con:
            count = con.execute("SELECT COUNT(*) as cnt FROM card_orders").fetchone()
        assert count["cnt"] == 0

    def test_번호판형식오류_영문혼합_400반환(self, client, seeded_db, molit_pass):
        # Given: 한국 표준형이 아닌 번호판
        payload = {"plate": "ABCD1234", "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 400

    def test_번호판_빈문자열_400반환(self, client, seeded_db, molit_pass):
        # Given: plate 빈값
        payload = {"plate": "", "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 400

    def test_차량없음_404반환(self, client, test_db, molit_pass):
        # Given: vehicles 에 차량 없이 토큰만 존재
        import database
        expires = (datetime.now() + timedelta(hours=24)).isoformat()
        with database.get_conn() as con:
            con.execute(
                "INSERT INTO tokens (access_token, car_id, hyundai_user_id, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (ACCESS_TOKEN, VALID_CAR_ID, "", expires),
            )
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 404

    def test_MOLIT검증실패_403반환(self, client, seeded_db, molit_fail):
        # Given: MOLIT 검증 실패 fixture
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 403

    def test_MOLIT검증실패_card_orders_저장안됨(self, client, seeded_db, molit_fail):
        # Given
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then: MOLIT 실패 후에도 order 가 저장되어선 안 된다
        import database
        with database.get_conn() as con:
            count = con.execute("SELECT COUNT(*) as cnt FROM card_orders").fetchone()
        assert count["cnt"] == 0

    def test_인증토큰없음_401반환(self, client, seeded_db, molit_pass):
        # Given: Authorization 헤더 없음
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload)

        # Then
        assert resp.status_code == 401

    def test_만료된토큰_401반환(self, client, test_db, molit_pass):
        # Given: 만료 시각이 과거인 토큰
        import database
        expired = (datetime.now() - timedelta(hours=1)).isoformat()
        with database.get_conn() as con:
            con.execute(
                "INSERT INTO vehicles (car_id, plate) VALUES (?, ?)", (VALID_CAR_ID, "")
            )
            con.execute(
                "INSERT INTO tokens (access_token, car_id, hyundai_user_id, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (ACCESS_TOKEN, VALID_CAR_ID, "", expired),
            )
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 401

    def test_이미등록된번호판_409반환(self, client, seeded_db, molit_pass):
        # Given: 다른 car_id 에 동일 번호판이 이미 매핑된 상태
        import database
        other_car_id = "car-other-001"
        with database.get_conn() as con:
            con.execute(
                "INSERT INTO vehicles (car_id, plate) VALUES (?, ?)",
                (other_car_id, VALID_PLATE),
            )
        payload = {"plate": VALID_PLATE, "bank_name": "", "agree_terms": True}

        # When
        resp = client.post("/card/order", json=payload, headers=AUTH_HEADER)

        # Then
        assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# UC-CARD-002 · POST /webhook/card
# ═══════════════════════════════════════════════════════════════════════════════

class TestCardWebhook:
    """UC-CARD-002: 카드 등록 완료 webhook 처리."""

    @pytest.fixture
    def db_with_order(self, seeded_db):
        """card_orders 에 pending order 를 미리 삽입한다."""
        import database
        with database.get_conn() as con:
            con.execute(
                "INSERT INTO card_orders (order_id, car_id, created_at) VALUES (?, ?, ?)",
                (ORDER_ID, VALID_CAR_ID, datetime.now().isoformat()),
            )
        return seeded_db

    @staticmethod
    def _webhook_payload(
        order_id: str = ORDER_ID,
        customer_key: str = CUSTOMER_KEY,
        payment_method_id: str = PAYMENT_METHOD_ID,
        card_brand: str = CARD_BRAND,
        last_four: str = LAST_FOUR,
        hmac_override: str | None = None,
    ) -> dict:
        sig = hmac_override or _make_hmac(
            order_id, customer_key, payment_method_id, card_brand, last_four
        )
        return {
            "order_id": order_id,
            "customer_key": customer_key,
            "payment_method_id": payment_method_id,
            "card_brand": card_brand,
            "last_four": last_four,
            "hmac": sig,
        }

    # ── 성공 케이스 ──────────────────────────────────────────────────────────

    def test_정상webhook_status_ok반환(self, client, db_with_order):
        # Given: 유효한 HMAC, DB 에 order 존재
        payload = self._webhook_payload()

        # When
        resp = client.post("/webhook/card", json=payload)

        # Then
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_정상webhook_payment_methods에_active_빌링키_저장됨(self, client, db_with_order):
        # Given
        payload = self._webhook_payload()

        # When
        client.post("/webhook/card", json=payload)

        # Then: payment_methods 에 is_default=1 인 active 결제수단이 저장되어야 한다
        import database
        with database.get_conn() as con:
            row = con.execute(
                "SELECT * FROM payment_methods WHERE car_id=? AND status='active'",
                (VALID_CAR_ID,),
            ).fetchone()
        assert row is not None
        assert row["payment_method_id"] == PAYMENT_METHOD_ID
        assert row["card_last_four"] == LAST_FOUR
        assert row["is_default"] == 1

    def test_정상webhook_card_orders_삭제됨(self, client, db_with_order):
        # Given
        payload = self._webhook_payload()

        # When
        client.post("/webhook/card", json=payload)

        # Then: 처리 완료 후 card_orders 에서 해당 order 가 삭제되어야 한다
        import database
        with database.get_conn() as con:
            row = con.execute(
                "SELECT order_id FROM card_orders WHERE order_id=?", (ORDER_ID,)
            ).fetchone()
        assert row is None

    def test_정상webhook_vehicles_카드정보_업데이트됨(self, client, db_with_order):
        # Given
        payload = self._webhook_payload()

        # When
        client.post("/webhook/card", json=payload)

        # Then: vehicles 테이블의 결제수단 관련 컬럼도 업데이트되어야 한다
        import database
        with database.get_conn() as con:
            row = con.execute(
                "SELECT customer_key, payment_method_id, card_last_four, card_brand"
                " FROM vehicles WHERE car_id=?",
                (VALID_CAR_ID,),
            ).fetchone()
        assert row["payment_method_id"] == PAYMENT_METHOD_ID
        assert row["card_last_four"] == LAST_FOUR
        assert row["card_brand"] == CARD_BRAND

    def test_카드재등록시_기존결제수단_is_default_해제됨(self, client, seeded_db):
        # Given: 첫 번째 카드 등록 후 두 번째 카드 등록
        import database
        first_order_id = "firstorder000000001"
        first_pm_id    = "pm-first-0001"
        with database.get_conn() as con:
            con.execute(
                "INSERT INTO card_orders (order_id, car_id, created_at) VALUES (?, ?, ?)",
                (first_order_id, VALID_CAR_ID, datetime.now().isoformat()),
            )
        first_hmac = _make_hmac(first_order_id, CUSTOMER_KEY, first_pm_id, CARD_BRAND, "9999")
        client.post("/webhook/card", json={
            "order_id": first_order_id, "customer_key": CUSTOMER_KEY,
            "payment_method_id": first_pm_id, "card_brand": CARD_BRAND,
            "last_four": "9999", "hmac": first_hmac,
        })

        with database.get_conn() as con:
            con.execute(
                "INSERT INTO card_orders (order_id, car_id, created_at) VALUES (?, ?, ?)",
                (ORDER_ID, VALID_CAR_ID, datetime.now().isoformat()),
            )

        # When: 두 번째 카드 webhook
        client.post("/webhook/card", json=self._webhook_payload())

        # Then: 기존 결제수단은 is_default=0, 신규는 is_default=1
        with database.get_conn() as con:
            old = con.execute(
                "SELECT is_default FROM payment_methods WHERE payment_method_id=?",
                (first_pm_id,),
            ).fetchone()
            new_ = con.execute(
                "SELECT is_default FROM payment_methods WHERE payment_method_id=?",
                (PAYMENT_METHOD_ID,),
            ).fetchone()
        assert old["is_default"] == 0
        assert new_["is_default"] == 1

    def test_중복webhook_두번_수신해도_payment_methods_중복저장_안됨(self, client, db_with_order):
        # Given: 동일 webhook 을 두 번 전송
        payload = self._webhook_payload()

        # When: 첫 번째는 200, 두 번째는 order 없음(404)
        client.post("/webhook/card", json=payload)
        client.post("/webhook/card", json=payload)

        # Then: payment_methods 에 해당 차량의 active 결제수단이 정확히 1건이어야 한다
        import database
        with database.get_conn() as con:
            count = con.execute(
                "SELECT COUNT(*) as cnt FROM payment_methods WHERE car_id=? AND status='active'",
                (VALID_CAR_ID,),
            ).fetchone()
        assert count["cnt"] == 1

    # ── 실패 케이스 ──────────────────────────────────────────────────────────

    def test_HMAC불일치_403반환(self, client, db_with_order):
        # Given: HMAC 이 잘못된 값
        payload = self._webhook_payload(hmac_override="invalid-hmac-value")

        # When
        resp = client.post("/webhook/card", json=payload)

        # Then
        assert resp.status_code == 403

    def test_HMAC불일치_payment_methods_저장안됨(self, client, db_with_order):
        # Given
        payload = self._webhook_payload(hmac_override="bad-hmac")

        # When
        client.post("/webhook/card", json=payload)

        # Then: HMAC 검증 실패 시 결제수단이 저장되어선 안 된다
        import database
        with database.get_conn() as con:
            count = con.execute(
                "SELECT COUNT(*) as cnt FROM payment_methods WHERE car_id=?",
                (VALID_CAR_ID,),
            ).fetchone()
        assert count["cnt"] == 0

    def test_없는order_id_404반환(self, client, seeded_db):
        # Given: card_orders 에 존재하지 않는 order_id (HMAC 은 해당 order_id 기준으로 올바르게 계산)
        nonexistent = "nonexistentorder001"
        payload = self._webhook_payload(
            order_id=nonexistent,
            hmac_override=_make_hmac(nonexistent, CUSTOMER_KEY, PAYMENT_METHOD_ID, CARD_BRAND, LAST_FOUR),
        )

        # When
        resp = client.post("/webhook/card", json=payload)

        # Then
        assert resp.status_code == 404

    def test_필수필드_order_id_누락_400반환(self, client, db_with_order):
        # Given: order_id 필드 없음
        payload = self._webhook_payload()
        del payload["order_id"]

        # When
        resp = client.post("/webhook/card", json=payload)

        # Then
        assert resp.status_code == 400

    def test_필수필드_hmac_누락_400반환(self, client, db_with_order):
        # Given: hmac 필드 없음
        payload = self._webhook_payload()
        del payload["hmac"]

        # When
        resp = client.post("/webhook/card", json=payload)

        # Then
        assert resp.status_code == 400

    def test_필수필드_payment_method_id_누락_400반환(self, client, db_with_order):
        # Given: payment_method_id 필드 없음
        payload = self._webhook_payload()
        del payload["payment_method_id"]

        # When
        resp = client.post("/webhook/card", json=payload)

        # Then
        assert resp.status_code == 400
