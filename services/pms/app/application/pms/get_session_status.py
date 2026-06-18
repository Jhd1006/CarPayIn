from dataclasses import dataclass


@dataclass(frozen=True)
class GetSessionStatusCommand:
    lot_id: str
    plate: str


@dataclass(frozen=True)
class GetSessionStatusResult:
    status: str  # "active" | "paid" | "not_found"


class GetSessionStatusService:
    def __init__(self, parking_session_store):
        self.parking_session_store = parking_session_store

    def execute(self, command: GetSessionStatusCommand) -> GetSessionStatusResult:
        if self.parking_session_store is None:
            return GetSessionStatusResult(status="not_found")
        session = self.parking_session_store.get_session(
            lot_id=command.lot_id, plate=command.plate
        )
        if session is None:
            return GetSessionStatusResult(status="not_found")
        return GetSessionStatusResult(status=session.get("status", "active"))
