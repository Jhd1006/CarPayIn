from fastapi import APIRouter, Depends

from app.api.deps import (
    get_calculate_fee_service,
    get_handle_lpr_entry_service,
    get_record_payment_complete_service,
    get_register_pre_notify_service,
)
from app.api.schemas.pms import (
    CalculateFeeResponse,
    LprEntryRequest,
    LprEntryResponse,
    PaymentCompleteRequest,
    PaymentCompleteResponse,
    PreRegisterRequest,
    PreRegisterResponse,
)
from app.application.pms.calculate_fee import CalculateFeeCommand, CalculateFeeService
from app.application.pms.handle_lpr_entry import (
    HandleLprEntryCommand,
    HandleLprEntryService,
)
from app.application.pms.record_payment_complete import (
    RecordPaymentCompleteCommand,
    RecordPaymentCompleteService,
)
from app.application.pms.register_pre_notify import (
    RegisterPreNotifyCommand,
    RegisterPreNotifyService,
)


router = APIRouter()


@router.post("/parking/pre-register", response_model=PreRegisterResponse)
def pre_register_plate(
    request: PreRegisterRequest,
    service: RegisterPreNotifyService = Depends(get_register_pre_notify_service),
) -> PreRegisterResponse:
    result = service.execute(
        RegisterPreNotifyCommand(lot_id=request.lot_id, plate=request.plate)
    )
    return PreRegisterResponse(
        status=result.status,
        lot_id=result.lot_id,
        plate=result.plate,
    )


@router.post("/lpr/entry", response_model=LprEntryResponse)
def handle_lpr_entry(
    request: LprEntryRequest,
    service: HandleLprEntryService = Depends(get_handle_lpr_entry_service),
) -> LprEntryResponse:
    result = service.execute(
        HandleLprEntryCommand(
            lot_id=request.lot_id,
            plate=request.plate,
            entry_time=request.entry_time,
        )
    )
    return LprEntryResponse(
        status=result.status,
        pms_session_id=result.pms_session_id,
    )


@router.get(
    "/pms/parking/fee",
    response_model=CalculateFeeResponse,
    response_model_exclude_none=True,
)
@router.get(
    "/parking/fee",
    response_model=CalculateFeeResponse,
    response_model_exclude_none=True,
)
def calculate_fee(
    lot_id: str | None = None,
    plate: str | None = None,
    pms_session_id: str | None = None,
    current_time: str | None = None,
    service: CalculateFeeService = Depends(get_calculate_fee_service),
) -> CalculateFeeResponse:
    result = service.execute(
        CalculateFeeCommand(
            pms_session_id=pms_session_id,
            current_time=current_time,
            lot_id=lot_id,
            plate=plate,
        )
    )
    return CalculateFeeResponse(
        pms_session_id=result.pms_session_id,
        lot_id=result.lot_id,
        plate=result.plate,
        amount=result.amount,
        duration_minutes=result.duration_minutes,
        currency=result.currency,
        entry_time=result.entry_time,
        calculated_at=result.calculated_at,
    )


@router.post(
    "/pms/payment/complete",
    response_model=PaymentCompleteResponse,
    response_model_exclude_none=True,
)
@router.post(
    "/payment/complete",
    response_model=PaymentCompleteResponse,
    response_model_exclude_none=True,
)
def record_payment_complete(
    request: PaymentCompleteRequest,
    service: RecordPaymentCompleteService = Depends(
        get_record_payment_complete_service,
    ),
) -> PaymentCompleteResponse:
    result = service.execute(
        RecordPaymentCompleteCommand(
            pms_session_id=request.pms_session_id,
            carpay_session_id=request.carpay_parking_session_id,
            tx_id=request.carpay_tx_id,
            amount=request.amount,
            currency=request.currency,
            approval_no=request.approval_no,
            idempotency_key=request.idempotency_key,
        )
    )
    return PaymentCompleteResponse(
        status=result.status,
        pms_session_id=request.pms_session_id,
        carpay_tx_id=request.carpay_tx_id,
    )
