import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, notification_publisher

router = APIRouter(tags=["Dev"])


@router.post("/dev/mock-payment-notification")
def mock_payment_notification(
    current_user: dict = Depends(get_current_user),
) -> dict:
    car_id = current_user["car_id"]
    notification_publisher.publish_payment_notification(
        session_id="sess_dev_001",
        car_id=car_id,
        lot_id="LOT_GANGNAM_01",
        tx_id=f"dev_tx_{uuid.uuid4().hex[:12]}",
        amount=3000,
        currency="KRW",
        approval_no="DEV-APPROVED",
    )
    return {"status": "ok"}
