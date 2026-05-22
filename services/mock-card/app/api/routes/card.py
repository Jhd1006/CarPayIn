from fastapi import APIRouter, Depends

from app.api.deps import (
    get_approve_card_payment_service,
    get_verify_and_tokenize_card_service,
)
from app.api.schemas.card import (
    CardChargeRequest,
    CardChargeResponse,
    CardVerifyRequest,
    CardVerifyResponse,
)
from app.application.card.approve_card_payment import (
    ApproveCardPaymentCommand,
    ApproveCardPaymentService,
)
from app.application.card.verify_and_tokenize_card import (
    VerifyAndTokenizeCardCommand,
    VerifyAndTokenizeCardService,
)


router = APIRouter(prefix="/cards")


@router.post("/verify", response_model=CardVerifyResponse)
def verify_card(
    request: CardVerifyRequest,
    service: VerifyAndTokenizeCardService = Depends(
        get_verify_and_tokenize_card_service,
    ),
) -> CardVerifyResponse:
    result = service.execute(
        VerifyAndTokenizeCardCommand(
            user_id=request.user_id,
            card_number=request.card_number,
            expiry=request.expiry,
            cvc=request.cvc,
        )
    )
    return CardVerifyResponse(
        card_token=result.card_token,
        last_four=result.last_four,
    )


@router.post("/charge", response_model=CardChargeResponse)
def charge_card(
    request: CardChargeRequest,
    service: ApproveCardPaymentService = Depends(get_approve_card_payment_service),
) -> CardChargeResponse:
    result = service.execute(
        ApproveCardPaymentCommand(
            card_token=request.card_token,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=request.idempotency_key,
        )
    )
    return CardChargeResponse(
        status=result.status,
        tx_id=result.tx_id,
        approval_no=result.approval_no,
    )
