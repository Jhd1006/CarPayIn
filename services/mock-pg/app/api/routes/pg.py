from html import escape
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    CardRegistrationSessionRequest,
    CardRegistrationSessionResponse,
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


def _pg_public_base_url(request: Request) -> str:
    configured = os.getenv("PG_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get(
        "x-forwarded-host",
        request.headers.get("host", request.url.netloc),
    )
    return f"{proto}://{host}".rstrip("/")


@router.post(
    "/pg/internal/card-registration/sessions",
    response_model=CardRegistrationSessionResponse,
)
@router.post(
    "/internal/card-registration/sessions",
    response_model=CardRegistrationSessionResponse,
)
def create_card_registration_session(
    request: Request,
    payload: CardRegistrationSessionRequest,
) -> CardRegistrationSessionResponse:
    if not payload.order_id.strip():
        raise HTTPException(status_code=400, detail="order_id_required")

    expires_at = datetime.utcnow() + timedelta(minutes=30)
    query = {"order_id": payload.order_id}
    if payload.card_brand:
        query["card_brand"] = payload.card_brand
    webview_url = f"{_pg_public_base_url(request)}/pg/card-register?{urlencode(query)}"

    return CardRegistrationSessionResponse(
        order_id=payload.order_id,
        webview_url=webview_url,
        pg_url=webview_url,
        expires_at=expires_at.isoformat(),
    )


@router.get("/pg/card-register", response_class=HTMLResponse)
@router.get("/card-register", response_class=HTMLResponse)
def card_registration_webview(
    order_id: str,
    card_brand: str = "현대카드",
) -> HTMLResponse:
    safe_order_id = escape(order_id, quote=True)
    safe_card_brand = escape(card_brand or "현대카드", quote=True)
    html = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Card Registration</title>
  <style>
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      background: linear-gradient(135deg, #f7faff 0%, #f4f7fb 52%, #fff8ef 100%);
      color: #191f28;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 20px;
    }
    .screen {
      width: 100%;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .shell {
      width: 100%;
      max-width: 360px;
    }
    .title {
      font-size: 20px;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0 0 4px;
    }
    .sub {
      color: #6b7684;
      font-size: 12px;
      margin: 0 0 18px;
    }
    .preview {
      width: 100%;
      height: 178px;
      border-radius: 8px;
      background: #3182f6;
      box-shadow: 0 16px 32px rgba(49, 130, 246, 0.24);
      color: #fff;
      margin-bottom: 18px;
      padding: 20px;
      position: relative;
      overflow: hidden;
      transition: background 180ms ease;
    }
    .preview:after {
      content: "";
      position: absolute;
      width: 160px;
      height: 160px;
      right: -52px;
      bottom: -64px;
      border-radius: 50%;
      border: 28px solid rgba(255, 255, 255, 0.12);
    }
    .brand-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12px;
      font-weight: 800;
      position: relative;
      z-index: 1;
    }
    .network { font-size: 14px; opacity: 0.9; }
    .chip {
      width: 38px;
      height: 28px;
      border-radius: 6px;
      background: linear-gradient(135deg, #f6d27a, #d8a834);
      margin-top: 18px;
      position: relative;
      z-index: 1;
    }
    .card-number {
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 18px;
      letter-spacing: 0;
      margin-top: 18px;
      position: relative;
      z-index: 1;
    }
    .valid-label {
      color: rgba(255, 255, 255, 0.68);
      font-size: 8px;
      margin-top: 16px;
      position: relative;
      z-index: 1;
    }
    .expiry-preview {
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 13px;
      margin-top: 2px;
      position: relative;
      z-index: 1;
    }
    .field { margin-bottom: 12px; }
    .row { display: grid; grid-template-columns: 1fr 104px; gap: 10px; }
    label {
      color: #6b7684;
      display: block;
      font-size: 11px;
      font-weight: 700;
      margin-bottom: 6px;
    }
    input {
      width: 100%;
      height: 48px;
      border: 1px solid #dce5f0;
      border-radius: 8px;
      background: #fff;
      color: #191f28;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 15px;
      outline: none;
      padding: 0 14px;
      box-shadow: 0 2px 10px rgba(25, 31, 40, 0.04);
    }
    input:focus { border-color: #3182f6; }
    input::placeholder { color: #adb5bd; }
    .actions { display: grid; gap: 8px; margin-top: 8px; }
    .primary, .secondary {
      border: 0;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 800;
      height: 50px;
    }
    .primary {
      background: #3182f6;
      color: #fff;
      box-shadow: 0 10px 18px rgba(49, 130, 246, 0.22);
    }
    .primary:disabled { opacity: 0.58; }
    .secondary {
      background: #ffffff;
      color: #3182f6;
      border: 1px solid #dce5f0;
    }
    .fine {
      color: #6b7684;
      font-size: 10px;
      line-height: 1.45;
      margin: 12px 0 0;
      text-align: center;
    }
    .result {
      display: none;
      align-items: center;
      flex-direction: column;
      justify-content: center;
      min-height: 100vh;
      text-align: center;
    }
    .mark {
      align-items: center;
      background: #e8f2ff;
      border-radius: 999px;
      color: #1b64da;
      display: flex;
      font-size: 34px;
      font-weight: 900;
      height: 72px;
      justify-content: center;
      margin-bottom: 16px;
      width: 72px;
    }
    .result-title {
      color: #1b64da;
      font-size: 20px;
      font-weight: 900;
      margin-bottom: 8px;
    }
    .result-sub { color: #6b7684; font-size: 13px; }
  </style>
</head>
<body>
  <main class="screen" id="registerView" data-order-id="__ORDER_ID__">
    <section class="shell">
      <h1 class="title">카드 등록</h1>
      <p class="sub"><span id="selectedBrandLabel">__CARD_BRAND__</span> · 카드 정보는 PG 화면에서만 처리됩니다.</p>

      <div class="preview" id="cardPreview">
        <div class="brand-row">
          <span id="previewBrand">HYUNDAI</span>
          <span class="network" id="previewNetwork">VISA</span>
        </div>
        <div class="chip"></div>
        <div class="card-number" id="previewNumber">0000 0000 0000 0000</div>
        <div class="valid-label">VALID THRU</div>
        <div class="expiry-preview" id="previewExpiry">MM/YY</div>
      </div>

      <form id="cardForm" novalidate>
        <div class="field">
          <label for="cardNumber">카드번호</label>
          <input id="cardNumber" name="card_number" autocomplete="cc-number"
                 placeholder="4111 1111 1111 1111" inputmode="numeric"
                 maxlength="23" pattern="[0-9 ]*">
        </div>
        <div class="row">
          <div class="field">
            <label for="cardExpiry">유효기간</label>
            <input id="cardExpiry" name="expiry" autocomplete="cc-exp"
                   placeholder="MM/YY" inputmode="numeric"
                   maxlength="5" pattern="[0-9/]*">
          </div>
          <div class="field">
            <label for="cardCvc">CVC</label>
            <input id="cardCvc" name="cvc" autocomplete="cc-csc"
                   placeholder="123" inputmode="numeric"
                   maxlength="4" pattern="[0-9]*">
          </div>
        </div>
        <div class="actions">
          <button class="primary" id="submitBtn" type="submit">등록하기</button>
          <button class="secondary" type="button" id="demoBtn">테스트 카드 입력</button>
        </div>
      </form>
      <p class="fine" id="statusText">카드번호, 유효기간, CVC 형식에 맞게 입력해 주세요.</p>
    </section>
  </main>

  <section class="result" id="successView">
    <div class="mark">✓</div>
    <div class="result-title">카드 등록 완료</div>
    <div class="result-sub" id="successSub">잠시 후 앱으로 돌아갑니다.</div>
  </section>

  <script>
    var selectedBrandName = "__CARD_BRAND__";
    var brandStyles = [
      { keys: ["현대카드", "HYUNDAI"], short: "HYUNDAI", bg: "#3182F6", network: "VISA" },
      { keys: ["KB국민", "KB"], short: "KB", bg: "#B8874A", network: "MASTER" },
      { keys: ["신한카드", "SHINHAN"], short: "SHINHAN", bg: "#E24B4B", network: "VISA" },
      { keys: ["삼성카드", "SAMSUNG"], short: "SAMSUNG", bg: "#2563EB", network: "MASTER" },
      { keys: ["롯데카드", "LOTTE"], short: "LOTTE", bg: "#D23F5B", network: "VISA" },
      { keys: ["우리카드", "WOORI"], short: "WOORI", bg: "#0B7FAB", network: "MASTER" },
      { keys: ["하나카드", "HANA"], short: "HANA", bg: "#0F8F68", network: "VISA" }
    ];
    var selectedBrand = resolveBrand(selectedBrandName);

    function $(id) { return document.getElementById(id); }
    function digitsOnly(value) { return String(value || "").replace(/\\D/g, ""); }
    function formatCardNumber(digits) {
      return digits.replace(/(.{4})/g, "$1 ").trim();
    }
    function formatCardNumberInput(value) {
      return formatCardNumber(digitsOnly(value).slice(0, 19));
    }
    function lastFour(value) {
      var digits = digitsOnly(value);
      if (!digits) return "0000";
      return ("0000" + digits.slice(-4)).slice(-4);
    }
    function resolveBrand(name) {
      var raw = String(name || "카드");
      var upper = raw.toUpperCase();
      for (var i = 0; i < brandStyles.length; i++) {
        var style = brandStyles[i];
        for (var j = 0; j < style.keys.length; j++) {
          if (upper.indexOf(style.keys[j].toUpperCase()) >= 0) {
            return { name: raw, short: style.short, bg: style.bg, network: style.network };
          }
        }
      }
      return { name: raw, short: "CARD", bg: "#3182F6", network: "VISA" };
    }
    function applyBrand() {
      $("selectedBrandLabel").textContent = selectedBrand.name;
      $("cardPreview").style.background = selectedBrand.bg;
      $("previewBrand").textContent = selectedBrand.short;
      $("previewNetwork").textContent = selectedBrand.network;
    }
    function refreshPreview() {
      var digits = digitsOnly($("cardNumber").value).slice(0, 19);
      $("previewNumber").textContent = formatCardNumber((digits + "0000000000000000").slice(0, 16));
      $("previewExpiry").textContent = $("cardExpiry").value.trim() || "MM/YY";
    }
    function showError(message) {
      $("statusText").textContent = message;
      $("statusText").style.color = "#E5484D";
    }
    function showInfo(message) {
      $("statusText").textContent = message;
      $("statusText").style.color = "#6B7684";
    }
    function expiryError(expiry) {
      if (!/^\\d{2}\\/\\d{2}$/.test(expiry)) return "유효기간은 MM/YY 형식으로 입력해 주세요.";
      var month = Number(expiry.slice(0, 2));
      var year = 2000 + Number(expiry.slice(3, 5));
      if (month < 1 || month > 12) return "유효기간 월은 01부터 12까지만 가능합니다.";
      var now = new Date();
      var currentYear = now.getFullYear();
      var currentMonth = now.getMonth() + 1;
      if (year < currentYear || (year === currentYear && month < currentMonth)) {
        return "이미 만료된 유효기간입니다.";
      }
      return "";
    }
    function validateInputs(cardDigits, expiry, cvc) {
      if (cardDigits.length < 13 || cardDigits.length > 19) {
        return "카드번호는 숫자 13~19자리로 입력해 주세요.";
      }
      var expiryMessage = expiryError(expiry);
      if (expiryMessage) return expiryMessage;
      if (!/^\\d{3,4}$/.test(cvc)) return "CVC는 숫자 3~4자리로 입력해 주세요.";
      return "";
    }
    $("cardNumber").addEventListener("input", function() {
      $("cardNumber").value = formatCardNumberInput($("cardNumber").value);
      refreshPreview();
    });
    $("cardExpiry").addEventListener("input", function() {
      var digits = digitsOnly($("cardExpiry").value).slice(0, 4);
      $("cardExpiry").value = digits.length > 2
        ? digits.slice(0, 2) + "/" + digits.slice(2)
        : digits;
      refreshPreview();
    });
    $("cardCvc").addEventListener("input", function() {
      $("cardCvc").value = digitsOnly($("cardCvc").value).slice(0, 4);
    });
    $("demoBtn").addEventListener("click", function() {
      $("cardNumber").value = "4111 1111 1111 1111";
      $("cardExpiry").value = "12/30";
      $("cardCvc").value = "123";
      showInfo("테스트 카드 정보가 입력되었습니다.");
      refreshPreview();
    });
    $("cardForm").addEventListener("submit", async function(event) {
      event.preventDefault();
      var button = $("submitBtn");
      var cardDigits = digitsOnly($("cardNumber").value);
      var expiry = $("cardExpiry").value.trim();
      var cvc = digitsOnly($("cardCvc").value);
      var validationMessage = validateInputs(cardDigits, expiry, cvc);
      if (validationMessage) {
        showError(validationMessage);
        return;
      }
      button.disabled = true;
      button.textContent = "처리 중...";
      showInfo("PG에서 결제수단을 등록하고 있습니다.");
      try {
        var response = await fetch("/pg/card-register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            order_id: $("registerView").dataset.orderId,
            card_number: cardDigits,
            expiry: expiry,
            cvc: cvc
          })
        });
        var body = await response.json();
        if (body.status !== "success") throw new Error("registration_failed");
        var four = lastFour(cardDigits);
        $("registerView").style.display = "none";
        $("successView").style.display = "flex";
        $("successSub").textContent = selectedBrand.name + " ****" + four + " 등록 완료";
        if (window.Android && window.Android.onRegistrationCompleteV3) {
          window.Android.onRegistrationCompleteV3($("registerView").dataset.orderId, four);
        }
      } catch (error) {
        showError("등록 실패. 다시 시도해 주세요.");
        button.disabled = false;
        button.textContent = "등록하기";
      }
    });
    applyBrand();
    refreshPreview();
  </script>
</body>
</html>"""
    return HTMLResponse(
        html.replace("__ORDER_ID__", safe_order_id).replace(
            "__CARD_BRAND__",
            safe_card_brand,
        )
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
