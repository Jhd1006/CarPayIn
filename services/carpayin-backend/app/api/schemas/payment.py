from pydantic import BaseModel


class ParkingFeeResponse(BaseModel):
    session_id: str
    lot_id: str
    amount: int
    duration: int
    currency: str
    entry_time: str
    status: str


class ProcessPaymentRequest(BaseModel):
    session_id: str
    amount: int
    currency: str


class ProcessPaymentResponse(BaseModel):
    status: str
    tx_id: str
    session_id: str | None = None
    approval_no: str | None = None
    failed_reason: str | None = None
    amount: int | None = None
    currency: str | None = None
