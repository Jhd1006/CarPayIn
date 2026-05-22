from pydantic import BaseModel


class PreNotifyRequest(BaseModel):
    car_id: str
    lot_id: str
    plate: str


class PreNotifyResponse(BaseModel):
    status: str
    car_id: str
    lot_id: str
    plate: str


class EntryWebhookRequest(BaseModel):
    pms_session_id: str
    lot_id: str
    plate: str
    entry_time: str


class EntryWebhookResponse(BaseModel):
    status: str
    session_id: str | None
    car_id: str | None = None
    lot_id: str
    entry_time: str
