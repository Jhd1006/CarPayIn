from fastapi import APIRouter, Depends

from app.api.deps import (
    get_charge_billing_key_service,
    get_complete_card_registration_service,
)
from app.api.schemas.pg import (
    BillingPaymentRequest,
    BillingPaymentResponse,
    CardRegistrationRequest,
    CardRegistrationResponse,
)
from app.application.pg.charge_billing_key import (
    ChargeBillingKeyCommand,
    ChargeBillingKeyService,
)
from app.application.pg.complete_card_registration import (
    CompleteCardRegistrationCommand,
    CompleteCardRegistrationService,
)


router = APIRouter()


@router.post("/card-register", response_model=CardRegistrationResponse)
def complete_card_registration(
    request: CardRegistrationRequest,
    service: CompleteCardRegistrationService = Depends(
        get_complete_card_registration_service,
    ),
) -> CardRegistrationResponse:
    result = service.execute(
        CompleteCardRegistrationCommand(
            order_id=request.order_id,
            card_number=request.card_number,
            expiry=request.expiry,
            cvc=request.cvc,
        )
    )
    return CardRegistrationResponse(
        status=result.status,
        billing_key=result.billing_key,
    )


@router.post("/payments/billing", response_model=BillingPaymentResponse)
def charge_billing_key(
    request: BillingPaymentRequest,
    service: ChargeBillingKeyService = Depends(get_charge_billing_key_service),
) -> BillingPaymentResponse:
    result = service.execute(
        ChargeBillingKeyCommand(
            billing_key=request.billing_key,
            amount=request.amount,
            currency=request.currency,
            idempotency_key=request.idempotency_key,
        )
    )
    return BillingPaymentResponse(
        status=result.status,
        tx_id=result.tx_id,
        approval_no=result.approval_no,
    )
