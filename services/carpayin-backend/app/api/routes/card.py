from fastapi import APIRouter, Depends

from app.api.deps import (
    get_create_card_order_service,
    get_current_user,
    get_handle_card_webhook_service,
)
from app.api.schemas.card import (
    CardOrderRequest,
    CardOrderResponse,
    CardWebhookRequest,
    CardWebhookResponse,
)
from app.application.card.create_card_order import (
    CreateCardOrderCommand,
    CreateCardOrderService,
)
from app.application.card.handle_card_webhook import (
    HandleCardWebhookCommand,
    HandleCardWebhookService,
)


router = APIRouter(prefix="/card", tags=["Card"])


@router.post("/order", response_model=CardOrderResponse)
def create_card_order(
    request: CardOrderRequest,
    current_user: dict = Depends(get_current_user),
    service: CreateCardOrderService = Depends(get_create_card_order_service),
) -> CardOrderResponse:
    result = service.execute(
        CreateCardOrderCommand(
            user_id=current_user["user_id"],
            car_id=current_user["car_id"],
            plate=request.plate,
            bank_name=request.bank_name,
            agree_terms=request.agree_terms,
        )
    )

    return CardOrderResponse(
        order_id=result.order_id,
        pg_url=result.pg_url,
        webview_url=result.pg_url,
    )


@router.post("/webhook", response_model=CardWebhookResponse)
def handle_card_webhook(
    request: CardWebhookRequest,
    service: HandleCardWebhookService = Depends(get_handle_card_webhook_service),
) -> CardWebhookResponse:
    result = service.execute(
        HandleCardWebhookCommand(
            order_id=request.order_id,
            billing_key=request.billing_key,
            card_last_four=request.card_last_four,
            status=request.status,
            signature=request.signature,
        )
    )

    return CardWebhookResponse(status=result.status)
