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
    .brands {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      overflow-x: auto;
      padding-bottom: 2px;
      scrollbar-width: none;
    }
    .brands::-webkit-scrollbar { display: none; }
    .brand-pill {
      background: #fff;
      border: 1px solid #dce5f0;
      border-radius: 8px;
      color: #4e5968;
      flex: 0 0 auto;
      font-size: 12px;
      font-weight: 700;
      height: 34px;
      padding: 0 13px;
    }
    .brand-pill.active {
      border-color: transparent;
      color: #fff;
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
    .result-title { color: #1b64da; font-size: 20px; font-weight: 900; margin-bottom: 8px; }
    .result-sub { color: #6b7684; font-size: 13px; }
  </style>
</head>
<body>
  <main class="screen" id="registerView" data-order-id="__ORDER_ID__">
    <section class="shell">
      <h1 class="title">카드 등록</h1>
      <p class="sub">Mock PG · 카드 정보는 PG 화면에서만 처리됩니다.</p>

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

      <div class="brands" id="brandList"></div>

      <form id="cardForm" novalidate>
        <div class="field">
          <label for="cardNumber">카드번호</label>
          <input id="cardNumber" name="card_number" autocomplete="cc-number"
                 placeholder="4111 1111 1111 1111" inputmode="text">
        </div>
        <div class="row">
          <div class="field">
            <label for="cardExpiry">유효기간</label>
            <input id="cardExpiry" name="expiry" autocomplete="cc-exp"
                   placeholder="12/30" inputmode="text">
          </div>
          <div class="field">
            <label for="cardCvc">CVC</label>
            <input id="cardCvc" name="cvc" autocomplete="cc-csc"
                   placeholder="123" inputmode="text">
          </div>
        </div>
        <div class="actions">
          <button class="primary" id="submitBtn" type="submit">등록하기</button>
          <button class="secondary" type="button" id="demoBtn">테스트 카드 입력</button>
        </div>
      </form>
      <p class="fine" id="statusText">로컬 데모에서는 가짜 입력값도 테스트 결제수단으로 등록됩니다.</p>
    </section>
  </main>

  <section class="result" id="successView">
    <div class="mark">✓</div>
    <div class="result-title">카드 등록 완료</div>
    <div class="result-sub" id="successSub">잠시 후 앱으로 돌아갑니다.</div>
  </section>

  <script>
    var brands = [
      { name: "현대카드", short: "HYUNDAI", bg: "#3182F6", color: "#FFFFFF", network: "VISA" },
      { name: "KB국민", short: "KB", bg: "#B8874A", color: "#FFF7E8", network: "MASTER" },
      { name: "신한카드", short: "SHINHAN", bg: "#E24B4B", color: "#FFF2F2", network: "VISA" },
      { name: "삼성카드", short: "SAMSUNG", bg: "#2563EB", color: "#EAF3FF", network: "MASTER" },
      { name: "롯데카드", short: "LOTTE", bg: "#D23F5B", color: "#FFF1F4", network: "VISA" },
      { name: "우리카드", short: "WOORI", bg: "#0B7FAB", color: "#E8F7FF", network: "MASTER" },
      { name: "하나카드", short: "HANA", bg: "#0F8F68", color: "#E8FFF6", network: "VISA" }
    ];
    var selectedBrand = brands[0];

    function $(id) { return document.getElementById(id); }
    function digitsOnly(value) { return String(value || "").replace(/\\D/g, ""); }
    function formatCardNumber(digits) {
      return digits.replace(/(.{4})/g, "$1 ").trim();
    }
    function lastFour(value) {
      var digits = digitsOnly(value);
      if (!digits) return "0000";
      return ("0000" + digits.slice(-4)).slice(-4);
    }
    function normalizeExpiry(value) {
      var text = String(value || "").trim();
      var digits = digitsOnly(text);
      if (!text) return "12/30";
      if (/^\\d{4}$/.test(digits)) return digits.slice(0, 2) + "/" + digits.slice(2);
      return text;
    }
    function renderBrands() {
      var list = $("brandList");
      list.innerHTML = "";
      brands.forEach(function(brand) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "brand-pill" + (brand === selectedBrand ? " active" : "");
        button.textContent = brand.name;
        if (brand === selectedBrand) button.style.background = brand.bg;
        button.onclick = function() { selectBrand(brand); };
        list.appendChild(button);
      });
    }
    function selectBrand(brand) {
      selectedBrand = brand;
      $("cardPreview").style.background = brand.bg;
      $("previewBrand").textContent = brand.short;
      $("previewNetwork").textContent = brand.network;
      renderBrands();
    }
    function refreshPreview() {
      var digits = digitsOnly($("cardNumber").value).slice(0, 19);
      $("previewNumber").textContent = formatCardNumber((digits + "0000000000000000").slice(0, 16));
      $("previewExpiry").textContent = $("cardExpiry").value.trim() || "MM/YY";
    }
    $("cardNumber").addEventListener("input", refreshPreview);
    $("cardExpiry").addEventListener("input", function() {
      var raw = $("cardExpiry").value;
      var digits = digitsOnly(raw).slice(0, 4);
      if (/^[\\d/\\s-]*$/.test(raw) && digits.length >= 3) {
        $("cardExpiry").value = digits.slice(0, 2) + "/" + digits.slice(2);
      }
      refreshPreview();
    });
    $("demoBtn").addEventListener("click", function() {
      $("cardNumber").value = "4111 1111 1111 1111";
      $("cardExpiry").value = "12/30";
      $("cardCvc").value = "123";
      refreshPreview();
    });
    $("cardForm").addEventListener("submit", async function(event) {
      event.preventDefault();
      var button = $("submitBtn");
      var status = $("statusText");
      var cardNumber = $("cardNumber").value.trim() || "0000";
      var expiry = normalizeExpiry($("cardExpiry").value);
      var cvc = $("cardCvc").value.trim() || "000";
      button.disabled = true;
      button.textContent = "처리 중...";
      status.textContent = "PG에서 결제수단을 등록하고 있습니다.";
      try {
        var response = await fetch("/pg/card-register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            order_id: $("registerView").dataset.orderId,
            card_number: cardNumber,
            expiry: expiry,
            cvc: cvc
          })
        });
        var body = await response.json();
        if (body.status !== "success") throw new Error("registration_failed");
        var four = lastFour(cardNumber);
        $("registerView").style.display = "none";
        $("successView").style.display = "flex";
        $("successSub").textContent = selectedBrand.name + " ****" + four + " 등록 완료";
        if (window.Android && window.Android.onRegistrationCompleteV3) {
          window.Android.onRegistrationCompleteV3($("registerView").dataset.orderId, four);
        }
      } catch (error) {
        status.textContent = "등록 실패. 다시 시도해 주세요.";
        button.disabled = false;
        button.textContent = "등록하기";
      }
    });
    selectBrand(brands[0]);
    refreshPreview();
  </script>
</body>
</html>"""
    return HTMLResponse(html.replace("__ORDER_ID__", safe_order_id))


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
