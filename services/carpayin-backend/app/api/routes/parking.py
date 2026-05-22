from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import (
    get_handle_entry_webhook_service,
    get_register_pre_notify_service,
)
from app.api.schemas.parking import (
    EntryWebhookRequest,
    EntryWebhookResponse,
    PreNotifyRequest,
    PreNotifyResponse,
)
from app.application.parking.handle_entry_webhook import (
    HandleEntryWebhookCommand,
    HandleEntryWebhookService,
)
from app.application.parking.register_pre_notify import (
    RegisterPreNotifyCommand,
    RegisterPreNotifyService,
)


router = APIRouter(tags=["Parking"])


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "missing_bearer_token",
            },
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "missing_bearer_token",
            },
        )
    return token


@router.post("/pre-notify", response_model=PreNotifyResponse)
def register_pre_notify(
    request: PreNotifyRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    service: RegisterPreNotifyService = Depends(get_register_pre_notify_service),
) -> PreNotifyResponse:
    result = service.execute(
        RegisterPreNotifyCommand(
            access_token=extract_bearer_token(authorization),
            car_id=request.car_id,
            lot_id=request.lot_id,
            plate=request.plate,
        )
    )

    return PreNotifyResponse(
        status=result.status,
        car_id=result.car_id,
        lot_id=result.lot_id,
        plate=result.plate,
    )


@router.post("/webhook/entry", response_model=EntryWebhookResponse)
def handle_entry_webhook(
    request: EntryWebhookRequest,
    pms_signature: str = Header(alias="X-PMS-Signature"),
    service: HandleEntryWebhookService = Depends(get_handle_entry_webhook_service),
) -> EntryWebhookResponse:
    result = service.execute(
        HandleEntryWebhookCommand(
            pms_token=pms_signature,
            pms_session_id=request.pms_session_id,
            lot_id=request.lot_id,
            plate=request.plate,
            entry_time=request.entry_time,
        )
    )

    return EntryWebhookResponse(
        status=result.status,
        session_id=result.session_id,
        lot_id=request.lot_id,
        entry_time=request.entry_time,
    )
