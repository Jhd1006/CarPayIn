from pydantic import BaseModel


class PreRegisterRequest(BaseModel):
    lot_id: str
    plate: str


class PreRegisterResponse(BaseModel):
    status: str
    lot_id: str
    plate: str


class LprEntryRequest(BaseModel):
    lot_id: str
    plate: str
    entry_time: str


class LprEntryResponse(BaseModel):
    status: str
    pms_session_id: str


class CalculateFeeResponse(BaseModel):
    pms_session_id: str | None = None
    lot_id: str | None = None
    plate: str | None = None
    amount: int
    duration_minutes: int | None = None
    currency: str
    entry_time: str | None = None
    calculated_at: str | None = None


class PaymentCompleteRequest(BaseModel):
    pms_session_id: str
    carpay_parking_session_id: str
    carpay_tx_id: str
    amount: int
    currency: str
    approval_no: str
    idempotency_key: str


class PaymentCompleteResponse(BaseModel):
    status: str
    pms_session_id: str | None = None
    carpay_tx_id: str | None = None


class LprExitRequest(BaseModel):
    lot_id: str
    plate: str


class LprExitResponse(BaseModel):
    status: str
    pms_session_id: str | None = None


class SessionStatusResponse(BaseModel):
    status: str  # "active" | "paid" | "not_found"
