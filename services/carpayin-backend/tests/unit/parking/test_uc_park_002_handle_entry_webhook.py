"""
입차 / 주차 세션 유스케이스 단위 테스트
UC-PARK-002: PMS 입차 webhook 처리
"""

import pytest
from datetime import datetime

from app.application.parking.handle_entry_webhook import (
    HandleEntryWebhookCommand,
    HandleEntryWebhookService,
)


VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:30:00"
VALID_CAR_ID = "car-001"
VALID_PMS_TOKEN = "pms-secret-token"


class FakePmsAuthValidator:
    def __init__(self):
        self.valid_tokens = {VALID_PMS_TOKEN}

    def validate(self, pms_token: str):
        if pms_token not in self.valid_tokens:
            raise ValueError("pms_auth_failed")


class FakePreNotifyStore:
    def __init__(self):
        self.pre_notifies = {}

    def add_pre_notify(self, lot_id: str, plate: str, car_id: str):
        key = f"{lot_id}:{plate}"
        self.pre_notifies[key] = {
            "lot_id": lot_id,
            "plate": plate,
            "car_id": car_id,
            "status": "incoming",
        }

    def get_pre_notify(self, lot_id: str, plate: str):
        key = f"{lot_id}:{plate}"
        return self.pre_notifies.get(key)

    def delete_pre_notify(self, lot_id: str, plate: str):
        key = f"{lot_id}:{plate}"
        if key in self.pre_notifies:
            del self.pre_notifies[key]


class FakeParkingSessionRepository:
    def __init__(self):
        self.sessions = {}
        self.sessions_by_car_id = {}

    def get_active_session_by_car_id(self, car_id: str):
        return self.sessions_by_car_id.get(car_id)

    def get_session_by_pms_session_id(self, pms_session_id: str):
        return self.sessions.get(pms_session_id)

    def create_session(
        self,
        *,
        session_id: str,
        pms_session_id: str,
        car_id: str,
        plate: str,
        lot_id: str,
        entry_time: str,
    ):
        session = {
            "session_id": session_id,
            "pms_session_id": pms_session_id,
            "car_id": car_id,
            "plate": plate,
            "lot_id": lot_id,
            "entry_time": entry_time,
            "status": "active",
        }
        self.sessions[pms_session_id] = session
        self.sessions_by_car_id[car_id] = session
        return session


class FakeNotificationPublisher:
    def __init__(self):
        self.published_messages = []

    def publish_entry_notification(
        self, *, session_id: str, car_id: str, lot_id: str, entry_time: str
    ):
        self.published_messages.append(
            {
                "type": "entry",
                "session_id": session_id,
                "car_id": car_id,
                "lot_id": lot_id,
                "entry_time": entry_time,
            }
        )


@pytest.fixture
def fake_pms_auth_validator():
    return FakePmsAuthValidator()


@pytest.fixture
def fake_pre_notify_store():
    return FakePreNotifyStore()


@pytest.fixture
def fake_parking_session_repository():
    return FakeParkingSessionRepository()


@pytest.fixture
def fake_notification_publisher():
    return FakeNotificationPublisher()


@pytest.fixture
def handle_entry_webhook_service(
    fake_pms_auth_validator,
    fake_pre_notify_store,
    fake_parking_session_repository,
    fake_notification_publisher,
):
    return HandleEntryWebhookService(
        pms_auth_validator=fake_pms_auth_validator,
        pre_notify_store=fake_pre_notify_store,
        parking_session_repository=fake_parking_session_repository,
        notification_publisher=fake_notification_publisher,
    )


class TestHandleEntryWebhook:
    """UC-PARK-002 - POST webhook/entry"""

    def test_pms_auth_failure_raises_error(self, handle_entry_webhook_service):
        """PMS 인증이 실패하면 401을 반환한다."""
        command = HandleEntryWebhookCommand(
            pms_token="invalid-token",
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        with pytest.raises(ValueError) as exc_info:
            handle_entry_webhook_service.execute(command)

        assert str(exc_info.value) == "pms_auth_failed"

    def test_pre_notify_exists_creates_active_session(
        self,
        handle_entry_webhook_service,
        fake_pre_notify_store,
        fake_parking_session_repository,
        fake_notification_publisher,
    ):
        """pre-notify가 있으면 active parking session을 만든다."""
        fake_pre_notify_store.add_pre_notify(VALID_LOT_ID, VALID_PLATE, VALID_CAR_ID)

        command = HandleEntryWebhookCommand(
            pms_token=VALID_PMS_TOKEN,
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        result = handle_entry_webhook_service.execute(command)

        # 세션 생성 확인
        session = fake_parking_session_repository.get_session_by_pms_session_id(
            VALID_PMS_SESSION_ID
        )
        assert session is not None
        assert session["status"] == "active"
        assert session["car_id"] == VALID_CAR_ID
        assert session["plate"] == VALID_PLATE
        assert session["lot_id"] == VALID_LOT_ID
        assert session["entry_time"] == VALID_ENTRY_TIME

        # pre-notify 삭제 확인
        assert fake_pre_notify_store.get_pre_notify(VALID_LOT_ID, VALID_PLATE) is None

        # 알림 발행 확인
        assert len(fake_notification_publisher.published_messages) == 1
        notification = fake_notification_publisher.published_messages[0]
        assert notification["type"] == "entry"
        assert notification["car_id"] == VALID_CAR_ID

        # 응답 확인
        assert result.status == "confirmed"
        assert result.session_id is not None

    def test_pre_notify_not_exists_returns_not_registered(
        self,
        handle_entry_webhook_service,
        fake_parking_session_repository,
    ):
        """pre-notify가 없으면 세션을 만들지 않고 not_registered를 반환한다."""
        command = HandleEntryWebhookCommand(
            pms_token=VALID_PMS_TOKEN,
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        result = handle_entry_webhook_service.execute(command)

        # 세션이 생성되지 않음
        session = fake_parking_session_repository.get_session_by_pms_session_id(
            VALID_PMS_SESSION_ID
        )
        assert session is None

        # 응답 확인
        assert result.status == "not_registered"
        assert result.session_id is None

    def test_duplicate_pms_session_id_does_not_create_duplicate_session(
        self,
        handle_entry_webhook_service,
        fake_pre_notify_store,
        fake_parking_session_repository,
    ):
        """같은 pms_session_id webhook이 중복되어도 세션이 중복 생성되지 않는다."""
        fake_pre_notify_store.add_pre_notify(VALID_LOT_ID, VALID_PLATE, VALID_CAR_ID)

        command = HandleEntryWebhookCommand(
            pms_token=VALID_PMS_TOKEN,
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        # 첫 번째 호출
        first_result = handle_entry_webhook_service.execute(command)
        first_session_id = first_result.session_id

        # pre-notify 다시 추가 (두 번째 webhook 시뮬레이션)
        fake_pre_notify_store.add_pre_notify(VALID_LOT_ID, VALID_PLATE, VALID_CAR_ID)

        # 두 번째 호출
        second_result = handle_entry_webhook_service.execute(command)

        # 같은 세션 ID 반환
        assert second_result.session_id == first_session_id
        assert second_result.status == "confirmed"

        # 세션이 하나만 존재
        assert len(fake_parking_session_repository.sessions) == 1

    def test_duplicate_car_id_active_session_returns_existing_result(
        self,
        handle_entry_webhook_service,
        fake_pre_notify_store,
        fake_parking_session_repository,
    ):
        """같은 car_id에 active session이 있으면 기존 결과를 반환한다."""
        # 기존 세션 생성
        existing_session_id = "existing-session-001"
        fake_parking_session_repository.create_session(
            session_id=existing_session_id,
            pms_session_id="old-pms-session",
            car_id=VALID_CAR_ID,
            plate=VALID_PLATE,
            lot_id=VALID_LOT_ID,
            entry_time="2026-05-20T13:00:00",
        )

        fake_pre_notify_store.add_pre_notify(VALID_LOT_ID, VALID_PLATE, VALID_CAR_ID)

        command = HandleEntryWebhookCommand(
            pms_token=VALID_PMS_TOKEN,
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
        )

        result = handle_entry_webhook_service.execute(command)

        # 기존 세션 ID 반환
        assert result.status == "confirmed"
        assert result.session_id == existing_session_id

        # 새 세션이 생성되지 않음
        assert len(fake_parking_session_repository.sessions) == 1

    def test_invalid_entry_time_format_raises_error(
        self,
        handle_entry_webhook_service,
        fake_pre_notify_store,
    ):
        """entry_time 형식이 잘못되면 400을 반환한다."""
        fake_pre_notify_store.add_pre_notify(VALID_LOT_ID, VALID_PLATE, VALID_CAR_ID)

        command = HandleEntryWebhookCommand(
            pms_token=VALID_PMS_TOKEN,
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time="invalid-time-format",
        )

        with pytest.raises(ValueError) as exc_info:
            handle_entry_webhook_service.execute(command)

        assert str(exc_info.value) == "invalid_entry_time_format"