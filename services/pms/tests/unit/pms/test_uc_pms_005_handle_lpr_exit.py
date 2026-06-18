"""
Mock PMS 유스케이스 단위 테스트
UC-PMS-005: LPR 출차 이벤트 처리
"""

import pytest

from app.application.pms.handle_lpr_exit import (
    HandleLprExitCommand,
    HandleLprExitService,
)


VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_PMS_SESSION_ID = "pms-sess-001"


class FakePmsSessionRepository:
    def __init__(self):
        self.sessions = {}
        self.exited = []

    def add_session(self, pms_session_id, lot_id, plate, status):
        self.sessions[(lot_id, plate)] = {
            "pms_session_id": pms_session_id,
            "lot_id": lot_id,
            "plate": plate,
            "status": status,
        }

    def get_paid_session_by_lot_and_plate(self, *, lot_id, plate):
        session = self.sessions.get((lot_id, plate))
        if session and session["status"] == "paid":
            return session
        return None

    def mark_exited(self, pms_session_id):
        self.exited.append(pms_session_id)


class FakeBarrierPublisher:
    def __init__(self):
        self.exit_calls = []

    def open_exit(self, *, pms_session_id):
        self.exit_calls.append(pms_session_id)


class FakeParkingSessionStore:
    def __init__(self, sessions=None):
        self._sessions = sessions or {}
        self.deleted = []

    def get_session(self, *, lot_id, plate):
        return self._sessions.get((lot_id, plate))

    def delete_session(self, *, lot_id, plate):
        self.deleted.append((lot_id, plate))


@pytest.fixture
def fake_pms_session_repository():
    return FakePmsSessionRepository()


@pytest.fixture
def fake_barrier():
    return FakeBarrierPublisher()


class TestHandleLprExit:
    """UC-PMS-005 - POST /lpr/exit"""

    def test_redis_paid_opens_barrier_and_exits(
        self, fake_pms_session_repository, fake_barrier
    ):
        """Redis에 paid 상태가 있으면 차단기를 열고 출차 처리한다."""
        store = FakeParkingSessionStore(
            sessions={
                (VALID_LOT_ID, VALID_PLATE): {
                    "pms_session_id": VALID_PMS_SESSION_ID,
                    "lot_id": VALID_LOT_ID,
                    "plate": VALID_PLATE,
                    "status": "paid",
                }
            }
        )
        service = HandleLprExitService(
            pms_session_repository=fake_pms_session_repository,
            barrier_publisher=fake_barrier,
            parking_session_store=store,
        )

        result = service.execute(HandleLprExitCommand(lot_id=VALID_LOT_ID, plate=VALID_PLATE))

        assert result.status == "opened"
        assert result.pms_session_id == VALID_PMS_SESSION_ID
        assert len(fake_barrier.exit_calls) == 1
        assert (VALID_LOT_ID, VALID_PLATE) in store.deleted
        assert VALID_PMS_SESSION_ID in fake_pms_session_repository.exited

    def test_redis_active_returns_not_paid(
        self, fake_pms_session_repository, fake_barrier
    ):
        """Redis에 active 상태(미결제)이면 차단기를 열지 않는다."""
        store = FakeParkingSessionStore(
            sessions={
                (VALID_LOT_ID, VALID_PLATE): {
                    "pms_session_id": VALID_PMS_SESSION_ID,
                    "lot_id": VALID_LOT_ID,
                    "plate": VALID_PLATE,
                    "status": "active",
                }
            }
        )
        service = HandleLprExitService(
            pms_session_repository=fake_pms_session_repository,
            barrier_publisher=fake_barrier,
            parking_session_store=store,
        )

        result = service.execute(HandleLprExitCommand(lot_id=VALID_LOT_ID, plate=VALID_PLATE))

        assert result.status == "not_paid"
        assert result.pms_session_id is None
        assert len(fake_barrier.exit_calls) == 0

    def test_redis_miss_db_paid_opens_barrier(
        self, fake_pms_session_repository, fake_barrier
    ):
        """Redis 키 없을 때 DB fallback으로 paid 세션을 찾아 차단기를 연다."""
        fake_pms_session_repository.add_session(
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            status="paid",
        )
        store = FakeParkingSessionStore()  # 빈 Redis
        service = HandleLprExitService(
            pms_session_repository=fake_pms_session_repository,
            barrier_publisher=fake_barrier,
            parking_session_store=store,
        )

        result = service.execute(HandleLprExitCommand(lot_id=VALID_LOT_ID, plate=VALID_PLATE))

        assert result.status == "opened"
        assert result.pms_session_id == VALID_PMS_SESSION_ID
        assert len(fake_barrier.exit_calls) == 1
        # DB fallback이므로 Redis delete는 호출되지 않음
        assert len(store.deleted) == 0
        assert VALID_PMS_SESSION_ID in fake_pms_session_repository.exited

    def test_redis_miss_db_no_paid_returns_not_found(
        self, fake_pms_session_repository, fake_barrier
    ):
        """Redis 키 없고 DB에도 paid 세션 없으면 not_found를 반환한다."""
        store = FakeParkingSessionStore()
        service = HandleLprExitService(
            pms_session_repository=fake_pms_session_repository,
            barrier_publisher=fake_barrier,
            parking_session_store=store,
        )

        result = service.execute(HandleLprExitCommand(lot_id=VALID_LOT_ID, plate=VALID_PLATE))

        assert result.status == "not_found"
        assert result.pms_session_id is None
        assert len(fake_barrier.exit_calls) == 0

    def test_no_redis_store_falls_back_to_db(
        self, fake_pms_session_repository, fake_barrier
    ):
        """parking_session_store가 없으면 DB를 바로 조회한다."""
        fake_pms_session_repository.add_session(
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            status="paid",
        )
        service = HandleLprExitService(
            pms_session_repository=fake_pms_session_repository,
            barrier_publisher=fake_barrier,
            parking_session_store=None,
        )

        result = service.execute(HandleLprExitCommand(lot_id=VALID_LOT_ID, plate=VALID_PLATE))

        assert result.status == "opened"
        assert result.pms_session_id == VALID_PMS_SESSION_ID
        assert len(fake_barrier.exit_calls) == 1
