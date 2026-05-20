from dataclasses import dataclass
from datetime import datetime
import uuid


@dataclass(frozen=True)
class HandleEntryWebhookCommand:
    pms_token: str
    pms_session_id: str
    lot_id: str
    plate: str
    entry_time: str


@dataclass(frozen=True)
class HandleEntryWebhookResult:
    status: str
    session_id: str | None


class HandleEntryWebhookService:
    def __init__(
        self,
        pms_auth_validator,
        pre_notify_store,
        parking_session_repository,
        notification_publisher,
    ):
        self.pms_auth_validator = pms_auth_validator
        self.pre_notify_store = pre_notify_store
        self.parking_session_repository = parking_session_repository
        self.notification_publisher = notification_publisher

    def execute(self, command: HandleEntryWebhookCommand) -> HandleEntryWebhookResult:
        # PMS 인증 검증
        self.pms_auth_validator.validate(command.pms_token)

        # entry_time 형식 검증
        try:
            datetime.fromisoformat(command.entry_time)
        except ValueError:
            raise ValueError("invalid_entry_time_format")

        # pms_session_id 중복 확인
        existing_session = self.parking_session_repository.get_session_by_pms_session_id(
            command.pms_session_id
        )
        if existing_session:
            return HandleEntryWebhookResult(
                status="confirmed",
                session_id=existing_session["session_id"],
            )

        # pre-notify 조회
        pre_notify = self.pre_notify_store.get_pre_notify(
            command.lot_id, command.plate
        )

        if not pre_notify:
            return HandleEntryWebhookResult(
                status="not_registered",
                session_id=None,
            )

        car_id = pre_notify["car_id"]

        # 동일 car_id의 active session 확인
        active_session = self.parking_session_repository.get_active_session_by_car_id(
            car_id
        )
        if active_session:
            return HandleEntryWebhookResult(
                status="confirmed",
                session_id=active_session["session_id"],
            )

        # 새 세션 생성
        session_id = str(uuid.uuid4())
        self.parking_session_repository.create_session(
            session_id=session_id,
            pms_session_id=command.pms_session_id,
            car_id=car_id,
            plate=command.plate,
            lot_id=command.lot_id,
            entry_time=command.entry_time,
        )

        # pre-notify 삭제
        self.pre_notify_store.delete_pre_notify(command.lot_id, command.plate)

        # 앱 알림 발행
        self.notification_publisher.publish_entry_notification(
            session_id=session_id,
            car_id=car_id,
            lot_id=command.lot_id,
            entry_time=command.entry_time,
        )

        return HandleEntryWebhookResult(
            status="confirmed",
            session_id=session_id,
        )