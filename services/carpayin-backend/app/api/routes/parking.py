from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import (
    get_handle_entry_webhook_service,
    get_register_pre_notify_service,
)
from app.api.schemas.parking import (
    EntryWebhookRequest,
    EntryWebhookResponse,
    ParkingLotResponse,
    ParkingLotsResponse,
    PreNotifyRequest,
    PreNotifyResponse,
    SimLocationRequest,
    SimLocationResponse,
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

PARTNER_PARKING_LOTS = [
    ParkingLotResponse(
        id="LOT_TEST_01",
        name="42dot 테스트 주차장",
        lat=37.48544722,
        lng=127.03636666,
    ),
    ParkingLotResponse(
        id="LOT_GANGNAM_01",
        name="강남 아이파킹",
        lat=37.4979,
        lng=127.0276,
    ),
    ParkingLotResponse(
        id="LOT_SEOCHO_01",
        name="서초 아이파킹",
        lat=37.4837,
        lng=127.0324,
    ),
    ParkingLotResponse(
        id="LOT_YEONGDEUNGPO_01",
        name="영등포 아이파킹",
        lat=37.5258,
        lng=126.8962,
    ),
]

_sim_location = SimLocationResponse(
    lat=37.48544722,
    lng=127.03636666,
    speed_kph=0.0,
    heading=0.0,
    source="default",
    updated_at=datetime.now(timezone.utc).isoformat(),
)


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


@router.get("/parking/lots", response_model=ParkingLotsResponse)
def get_parking_lots() -> ParkingLotsResponse:
    return ParkingLotsResponse(lots=PARTNER_PARKING_LOTS)


@router.post("/sim/location", response_model=SimLocationResponse)
def update_sim_location(request: SimLocationRequest) -> SimLocationResponse:
    global _sim_location
    _sim_location = SimLocationResponse(
        lat=request.lat,
        lng=request.lng,
        speed_kph=request.speed_kph,
        heading=request.heading,
        source=request.source,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    return _sim_location


@router.get("/sim/location", response_model=SimLocationResponse)
def get_sim_location() -> SimLocationResponse:
    return _sim_location


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
