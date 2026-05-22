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
    amount: int
    duration_minutes: int
    currency: str


class PaymentCompleteRequest(BaseModel):
    pms_session_id: str
    carpay_session_id: str
    tx_id: str
    amount: int
    currency: str
    approval_no: str
    idempotency_key: str


class PaymentCompleteResponse(BaseModel):
    status: str
