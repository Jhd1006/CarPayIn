from pydantic import BaseModel


class CardRegistrationSessionRequest(BaseModel):
    order_id: str
    car_id: str = ""
    plate: str = ""
    card_brand: str = ""
    callback_url: str = ""


class CardRegistrationSessionResponse(BaseModel):
    order_id: str
    webview_url: str
    pg_url: str
    expires_at: str = ""


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
