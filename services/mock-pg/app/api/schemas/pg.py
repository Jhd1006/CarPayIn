from pydantic import BaseModel


class CardRegistrationRequest(BaseModel):
    order_id: str
    card_number: str
    expiry: str
    cvc: str


class CardRegistrationResponse(BaseModel):
    status: str
    billing_key: str | None = None


class BillingPaymentRequest(BaseModel):
    billing_key: str
    amount: int
    currency: str
    idempotency_key: str


class BillingPaymentResponse(BaseModel):
    status: str
    pg_tx_id: str
    approval_no: str | None = None
    failed_reason: str | None = None
