"""
Mock PMS 유스케이스 단위 테스트
UC-PMS-001: 차량번호 사전 등록
"""

import pytest

from app.application.pms.register_pre_notify import (
    RegisterPreNotifyCommand,
    RegisterPreNotifyService,
)


VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"


class FakePreRegistrationRepository:
    def __init__(self):
        self.pre_registrations = {}

    def save_pre_registration(self, *, lot_id: str, plate: str):
        key = f"{lot_id}:{plate}"
        if key not in self.pre_registrations:
            self.pre_registrations[key] = {
                "lot_id": lot_id,
                "plate": plate,
                "status": "pre_registered",
            }
        return self.pre_registrations[key]

    def get_pre_registration(self, *, lot_id: str, plate: str):
        key = f"{lot_id}:{plate}"
        return self.pre_registrations.get(key)


@pytest.fixture
def fake_pre_registration_repository():
    return FakePreRegistrationRepository()


@pytest.fixture
def register_pre_notify_service(fake_pre_registration_repository):
    return RegisterPreNotifyService(
        pre_registration_repository=fake_pre_registration_repository,
    )


class TestRegisterPreNotify:
    """UC-PMS-001 - POST /pms/parking/pre-register"""

    def test_valid_plate_is_pre_registered(
        self,
        register_pre_notify_service,
        fake_pre_registration_repository,
    ):
        """유효한 plate를 사전 등록한다."""
        command = RegisterPreNotifyCommand(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        result = register_pre_notify_service.execute(command)

        # 저장 확인
        saved = fake_pre_registration_repository.get_pre_registration(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )
        assert saved is not None
        assert saved["lot_id"] == VALID_LOT_ID
        assert saved["plate"] == VALID_PLATE
        assert saved["status"] == "pre_registered"

        # 응답 확인
        assert result.status == "registered"
        assert result.lot_id == VALID_LOT_ID
        assert result.plate == VALID_PLATE

    def test_duplicate_plate_and_lot_id_is_idempotent(
        self,
        register_pre_notify_service,
        fake_pre_registration_repository,
    ):
        """같은 plate와 lot_id 중복 요청은 멱등 처리된다."""
        command = RegisterPreNotifyCommand(
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
        )

        # 첫 번째 요청
        first_result = register_pre_notify_service.execute(command)

        # 두 번째 요청
        second_result = register_pre_notify_service.execute(command)

        # 같은 결과 반환
        assert first_result.status == second_result.status
        assert first_result.lot_id == second_result.lot_id
        assert first_result.plate == second_result.plate

        # 중복 저장되지 않음 (1개만 존재)
        all_registrations = fake_pre_registration_repository.pre_registrations
        assert len(all_registrations) == 1