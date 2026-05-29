from html import escape

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse

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


@router.get("/pg/card-register", response_class=HTMLResponse)
@router.get("/card-register", response_class=HTMLResponse)
def card_registration_webview(order_id: str) -> HTMLResponse:
    safe_order_id = escape(order_id, quote=True)
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Register card</title></head>
<body>
  <main id="registration" data-order-id="{safe_order_id}">
    <h1>Register card</h1>
    <form id="card-form">
      <label>Card number <input name="card_number" autocomplete="cc-number" required></label>
      <label>Expiry <input name="expiry" placeholder="MM/YY" autocomplete="cc-exp" required></label>
      <label>CVC <input name="cvc" autocomplete="cc-csc" required></label>
      <button type="submit">Register</button>
    </form>
    <p id="result" role="status"></p>
  </main>
  <script>
    const root = document.getElementById("registration");
    const form = document.getElementById("card-form");
    const result = document.getElementById("result");
    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const fields = new FormData(form);
      const response = await fetch("/pg/card-register", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          order_id: root.dataset.orderId,
          card_number: fields.get("card_number"),
          expiry: fields.get("expiry"),
          cvc: fields.get("cvc")
        }})
      }});
      const body = await response.json();
      result.textContent = body.status === "success"
        ? "Card registration complete."
        : "Card registration failed.";
    }});
  </script>
</body>
</html>"""
    )


@router.post("/pg/card-register", response_model=CardRegistrationResponse)
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


@router.post(
    "/pg/payments/billing",
    response_model=BillingPaymentResponse,
    response_model_exclude_none=True,
)
@router.post(
    "/payments/billing",
    response_model=BillingPaymentResponse,
    response_model_exclude_none=True,
)
def charge_billing_key(
    request: BillingPaymentRequest,
    response: Response,
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
    if result.status == "failed":
        response.status_code = 400

    return BillingPaymentResponse(
        status=result.status,
        pg_tx_id=result.tx_id,
        approval_no=result.approval_no,
        failed_reason=None if result.status == "success" else "payment_failed",
    )
