"""
Mock PMS 유스케이스 단위 테스트
UC-PMS-002: LPR 입차 이벤트로 PMS 세션 생성
"""

import pytest
from datetime import datetime

from app.application.pms.handle_lpr_entry import (
    HandleLprEntryCommand,
    HandleLprEntryService,
)


VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"


class FakePreRegistrationStore:
    def __init__(self):
        self.registrations = {
            (VALID_LOT_ID, VALID_PLATE): {
                "lot_id": VALID_LOT_ID,
                "plate": VALID_PLATE,
            }
        }

    def get_active_pre_registration(self, *, lot_id: str, plate: str):
        return self.registrations.get((lot_id, plate))

    def consume_pre_registration(self, *, lot_id: str, plate: str):
        self.registrations.pop((lot_id, plate), None)


class FakePmsSessionRepository:
    def __init__(self):
        self.sessions = {}

    def get_active_session_by_plate(self, plate: str):
        for session in self.sessions.values():
            if session["plate"] == plate and session["status"] == "active":
                return session
        return None

    def create_session(
        self,
        *,
        pms_session_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
    ):
        self.sessions[pms_session_id] = {
            "pms_session_id": pms_session_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
            "status": "active",
        }
        return self.sessions[pms_session_id]


class FakeBarrierPublisher:
    def __init__(self):
        self.entry_calls = []
        self.exit_calls = []

    def open_entry(self, *, pms_session_id: str = ""):
        self.entry_calls.append(pms_session_id)

    def open_exit(self, *, pms_session_id: str = ""):
        self.exit_calls.append(pms_session_id)


class FakeCarPayInWebhookClient:
    def __init__(self):
        self.webhook_calls = []

    def send_entry_webhook(
        self,
        *,
        pms_session_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
    ):
        self.webhook_calls.append(
            {
                "pms_session_id": pms_session_id,
                "lot_id": lot_id,
                "plate": plate,
                "entry_time": entry_time,
            }
        )


@pytest.fixture
def fake_pre_registration_repository():
    return FakePreRegistrationStore()


@pytest.fixture
def fake_pms_session_repository():
    return FakePmsSessionRepository()


@pytest.fixture
def fake_carpayin_webhook_client():
    return FakeCarPayInWebhookClient()


@pytest.fixture
def handle_lpr_entry_service(
    fake_pre_registration_repository,
    fake_pms_session_repository,
    fake_carpayin_webhook_client,
):
    return HandleLprEntryService(
        pre_registration_repository=fake_pre_registration_repository,
        pms_session_repository=fake_pms_session_repository,
        carpayin_webhook_client=fake_carpayin_webhook_client,
    )


class TestHandleLprEntry:
    """UC-PMS-002 - LPR 입차 이벤트로 PMS 세션 생성"""

    def test_creates_active_pms_session(
        self,
        handle_lpr_entry_service,
        fake_pre_registration_repository,
        fake_pms_session_repository,
    ):
        """active PMS session을 생성한다."""
        command = HandleLprEntryCommand(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        result = handle_lpr_entry_service.execute(command)

        # 세션 생성 확인
        session = fake_pms_session_repository.sessions[result.pms_session_id]
        assert session is not None
        assert session["lot_id"] == VALID_LOT_ID
        assert session["plate"] == VALID_PLATE
        assert session["entry_time"] == VALID_ENTRY_TIME
        assert session["status"] == "active"

        # 응답 확인
        assert result.status == "created"
        assert result.pms_session_id is not None
        assert (
            fake_pre_registration_repository.registrations[
                (VALID_LOT_ID, VALID_PLATE)
            ]["status"]
            == "consumed"
        )

    def test_duplicate_plate_does_not_create_duplicate_session(
        self,
        handle_lpr_entry_service,
        fake_pms_session_repository,
        fake_carpayin_webhook_client,
    ):
        """같은 plate에 active session이 있으면 중복 생성하지 않는다."""
        command = HandleLprEntryCommand(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        # 첫 번째 요청
        first_result = handle_lpr_entry_service.execute(command)
        first_session_id = first_result.pms_session_id

        # 두 번째 요청
        second_result = handle_lpr_entry_service.execute(command)

        # 기존 세션 ID 반환
        assert second_result.pms_session_id == first_session_id
        assert second_result.status == "existing"

        # 세션이 하나만 존재, webhook은 첫 번째 요청에서만 발생
        assert len(fake_pms_session_repository.sessions) == 1
        assert len(fake_carpayin_webhook_client.webhook_calls) == 1

    def test_webhook_payload_contains_required_fields(
        self,
        handle_lpr_entry_service,
        fake_carpayin_webhook_client,
    ):
        """webhook payload에 pms_session_id, lot_id, plate, entry_time이 포함된다."""
        command = HandleLprEntryCommand(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        result = handle_lpr_entry_service.execute(command)

        # 웹훅 호출 확인
        assert len(fake_carpayin_webhook_client.webhook_calls) == 1
        webhook_payload = fake_carpayin_webhook_client.webhook_calls[0]

        # 필수 필드 확인
        assert webhook_payload["pms_session_id"] == result.pms_session_id
        assert webhook_payload["lot_id"] == VALID_LOT_ID
        assert webhook_payload["plate"] == VALID_PLATE
        assert webhook_payload["entry_time"] == VALID_ENTRY_TIME

    def test_unregistered_plate_creates_session_without_webhook(
        self,
        handle_lpr_entry_service,
        fake_pms_session_repository,
        fake_carpayin_webhook_client,
    ):
        """사전등록 안 된 차량도 세션은 생성하되 webhook은 전송하지 않는다."""
        command = HandleLprEntryCommand(
            lot_id=VALID_LOT_ID,
            plate="99UNKNOWN",
            entry_time=VALID_ENTRY_TIME,
        )

        result = handle_lpr_entry_service.execute(command)

        assert result.status == "created"
        assert result.pms_session_id is not None
        assert len(fake_carpayin_webhook_client.webhook_calls) == 0

    def test_entry_barrier_opens_on_lpr(
        self,
        fake_pre_registration_repository,
        fake_pms_session_repository,
        fake_carpayin_webhook_client,
    ):
        """LPR 인식 시 사전등록 여부와 무관하게 입구 차단기가 열린다."""
        barrier = FakeBarrierPublisher()
        service = HandleLprEntryService(
            pre_registration_repository=fake_pre_registration_repository,
            pms_session_repository=fake_pms_session_repository,
            carpayin_webhook_client=fake_carpayin_webhook_client,
            barrier_publisher=barrier,
        )
        command = HandleLprEntryCommand(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        service.execute(command)

        assert len(barrier.entry_calls) == 1
        assert len(barrier.exit_calls) == 0

    def test_entry_barrier_opens_even_for_unregistered_plate(
        self,
        fake_pre_registration_repository,
        fake_pms_session_repository,
        fake_carpayin_webhook_client,
    ):
        """사전등록 안 된 차량도 입구 차단기가 열리고 세션이 생성된다."""
        barrier = FakeBarrierPublisher()
        service = HandleLprEntryService(
            pre_registration_repository=fake_pre_registration_repository,
            pms_session_repository=fake_pms_session_repository,
            carpayin_webhook_client=fake_carpayin_webhook_client,
            barrier_publisher=barrier,
        )
        command = HandleLprEntryCommand(
            lot_id=VALID_LOT_ID,
            plate="99UNKNOWN",
            entry_time=VALID_ENTRY_TIME,
        )

        result = service.execute(command)

        assert result.status == "created"
        assert len(barrier.entry_calls) == 1
        assert len(fake_carpayin_webhook_client.webhook_calls) == 0
