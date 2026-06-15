from fastapi import APIRouter, Depends, Header, Response

from app.api.deps import get_parking_fee_service, get_process_payment_service
from app.api.schemas.payment import (
    ParkingFeeResponse,
    ProcessPaymentRequest,
    ProcessPaymentResponse,
)
from app.api.utils import extract_bearer_token
from app.application.payment.get_parking_fee import (
    GetParkingFeeCommand,
    GetParkingFeeService,
)
from app.application.payment.process_payment import (
    ProcessPaymentCommand,
    ProcessPaymentService,
)


router = APIRouter(tags=["Payment"])


@router.get("/fee/{session_id}", response_model=ParkingFeeResponse)
def get_parking_fee(
    session_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    service: GetParkingFeeService = Depends(get_parking_fee_service),
) -> ParkingFeeResponse:
    result = service.execute(
        GetParkingFeeCommand(
            access_token=extract_bearer_token(authorization),
            session_id=session_id,
        )
    )

    return ParkingFeeResponse(
        session_id=result.session_id,
        lot_id=result.lot_id,
        amount=result.amount,
        duration=result.duration,
        currency=result.currency,
        entry_time=result.entry_time,
        status=result.status,
    )


@router.post(
    "/payment",
    response_model=ProcessPaymentResponse,
    response_model_exclude_none=True,
)
def process_payment(
    request: ProcessPaymentRequest,
    response: Response,
    authorization: str | None = Header(default=None, alias="Authorization"),
    service: ProcessPaymentService = Depends(get_process_payment_service),
) -> ProcessPaymentResponse:
    result = service.execute(
        ProcessPaymentCommand(
            access_token=extract_bearer_token(authorization),
            session_id=request.session_id,
            amount=request.amount,
            currency=request.currency,
        )
    )

    if result.status == "failed":
        response.status_code = 402

    return ProcessPaymentResponse(
        status=result.status,
        tx_id=result.tx_id,
        session_id=result.session_id or request.session_id,
        approval_no=result.approval_no if result.status == "success" else None,
        failed_reason=result.failed_reason,
        amount=(
            result.amount if result.amount is not None else request.amount
        )
        if result.status == "success"
        else None,
        currency=(result.currency or request.currency)
        if result.status == "success"
        else None,
    )
