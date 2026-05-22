from pydantic import BaseModel


class CardVerifyRequest(BaseModel):
    user_id: str
    card_number: str
    expiry: str
    cvc: str


class CardVerifyResponse(BaseModel):
    card_token: str
    last_four: str


class CardChargeRequest(BaseModel):
    card_token: str
    amount: int
    currency: str
    idempotency_key: str


class CardChargeResponse(BaseModel):
    status: str
    tx_id: str
    approval_no: str | None = None
