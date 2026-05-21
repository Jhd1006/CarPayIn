"""
Mock PMS 유스케이스 단위 테스트
UC-PMS-003: 현재 요금 계산
"""

import pytest
from datetime import datetime, timedelta

from app.application.pms.calculate_fee import (
    CalculateFeeCommand,
    CalculateFeeService,
)


VALID_PMS_SESSION_ID = "pms-sess-001"
VALID_LOT_ID = "LOT_GN_01"
VALID_PLATE = "12가3456"
VALID_ENTRY_TIME = "2026-05-20T14:00:00"
CURRENT_TIME = "2026-05-20T15:30:00"


class FakePmsSessionRepository:
    def __init__(self):
        self.sessions = {}

    def add_session(
        self,
        pms_session_id: str,
        lot_id: str,
        plate: str,
        entry_time: str,
        status: str = "active",
    ):
        self.sessions[pms_session_id] = {
            "pms_session_id": pms_session_id,
            "lot_id": lot_id,
            "plate": plate,
            "entry_time": entry_time,
            "status": status,
        }

    def get_session_by_id(self, pms_session_id: str):
        return self.sessions.get(pms_session_id)


class FakeFeeCalculator:
    def calculate(self, entry_time: str, current_time: str) -> dict:
        entry = datetime.fromisoformat(entry_time)
        current = datetime.fromisoformat(current_time)
        duration_minutes = int((current - entry).total_seconds() / 60)
        
        # 30분당 500원
        blocks = (duration_minutes + 29) // 30  # 올림
        amount = blocks * 500
        
        return {
            "amount": amount,
            "duration_minutes": duration_minutes,
        }


@pytest.fixture
def fake_pms_session_repository():
    return FakePmsSessionRepository()


@pytest.fixture
def fake_fee_calculator():
    return FakeFeeCalculator()


@pytest.fixture
def calculate_fee_service(
    fake_pms_session_repository,
    fake_fee_calculator,
):
    return CalculateFeeService(
        pms_session_repository=fake_pms_session_repository,
        fee_calculator=fake_fee_calculator,
    )


class TestCalculateFee:
    """UC-PMS-003 - GET /parking/fee"""

    def test_active_session_returns_amount_and_duration(
        self,
        calculate_fee_service,
        fake_pms_session_repository,
    ):
        """active session이면 amount와 duration을 반환한다."""
        fake_pms_session_repository.add_session(
            pms_session_id=VALID_PMS_SESSION_ID,
            lot_id=VALID_LOT_ID,
            plate=VALID_PLATE,
            entry_time=VALID_ENTRY_TIME,
            status="active",
        )

        command = CalculateFeeCommand(
            pms_session_id=VALID_PMS_SESSION_ID,
            current_time=CURRENT_TIME,
        )

        result = calculate_fee_service.execute(command)

        # 요금 계산 확인 (90분 = 30분 3블록 = 1500원)
        assert result.amount == 1500
        assert result.duration_minutes == 90
        assert result.currency == "KRW"

    def test_session_not_found_raises_error(
        self,
        calculate_fee_service,
    ):
        """session이 없으면 404를 반환한다."""
        command = CalculateFeeCommand(
            pms_session_id="non-existent-session",
            current_time=CURRENT_TIME,
        )

        with pytest.raises(ValueError) as exc_info:
            calculate_fee_service.execute(command)

        assert str(exc_info.value) == "session_not_found"