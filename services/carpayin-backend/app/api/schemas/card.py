from typing import Literal

from pydantic import BaseModel, StrictBool


class CardOrderRequest(BaseModel):
    plate: str
    bank_name: str
    agree_terms: StrictBool


class CardOrderResponse(BaseModel):
    order_id: str
    pg_url: str


class CardWebhookRequest(BaseModel):
    order_id: str
    billing_key: str
    card_last_four: str
    status: Literal["active"]
    signature: str


class CardWebhookResponse(BaseModel):
    status: str
