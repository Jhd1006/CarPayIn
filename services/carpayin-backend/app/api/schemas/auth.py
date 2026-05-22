from pydantic import BaseModel


class QrSessionCreateRequest(BaseModel):
    login_session_id: str
    vin_hash: str


class QrSessionCreateResponse(BaseModel):
    login_url: str


class HyundaiOAuthCallbackResponse(BaseModel):
    status: str
    session_id: str


class SessionStatusResponse(BaseModel):
    status: str
    user_id: str | None = None
    name: str | None = None
    cars: list[dict] | None = None
    temp_access_token: str | None = None
