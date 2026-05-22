# API 테스트 코드 작성 컨벤션

## 0. 파일명

API 테스트 파일명에는 유스케이스 번호를 포함한다. 파일명만 보고 어떤 API 유스케이스 테스트인지 알 수 있어야 한다.

API 테스트 파일명은 unit test와 동일한 규칙을 따른다.

```text
test_uc_{domain}_{number}_{use_case_name}.py
```

예:

```text
test_uc_auth_001_create_qr_session.py
test_uc_auth_006_refresh_access_token.py
test_uc_card_001_create_card_order.py
test_uc_card_002_handle_card_webhook.py
test_uc_park_001_register_pre_notify.py
test_uc_pay_001_get_parking_fee.py
```

하나의 API 흐름에서 여러 유스케이스를 함께 검증해야 자연스러운 경우에는 연관된 유스케이스 번호를 모두 파일명에 포함한다.

예:

```text
test_uc_card_api_001_002_card_order_and_webhook.py
```

## 1. 테스트 위치

API 테스트는 `tests/api/` 아래에 domain별로 분리한다.

```text
tests/
  api/
    auth/
      test_uc_auth_001_create_qr_session.py
      test_uc_auth_006_refresh_access_token.py
    card/
      test_uc_card_api_001_002_card_order_and_webhook.py
    parking/
      test_uc_park_001_register_pre_notify.py
    payment/
      test_uc_pay_001_get_parking_fee.py
```

API 테스트 파일에서는 HTTP API 계약만 검증한다. 실제 DB, Redis, 외부 API 연동 검증은 `tests/integration/`에서 다룬다.

이 프로젝트에서는 API test와 integration test를 분리한다. API test는 FastAPI route, request/response schema, status code, auth guard, exception handler처럼 HTTP layer의 계약을 검증한다. Integration test는 repository, DB, Redis, 외부 client adapter처럼 실제 인프라와 연결되는 구현을 검증한다.

## 2. API Test의 역할

API test는 HTTP 계약을 검증한다. unit test와 역할이 다르다.

| 검증 대상 | Unit Test | API Test |
| --- | --- | --- |
| 비즈니스 규칙 | O | X |
| HTTP status code | X | O |
| request body 파싱과 직렬화 | X | O |
| response body 스키마 | X | O |
| auth guard | X | O |
| Pydantic 파싱 실패 | X | O |
| service 예외의 HTTP 변환 | X | O |

unit test에서 이미 검증한 비즈니스 세부 규칙을 API test에서 반복하지 않는다.

예를 들어 `agree_terms`가 false일 때 실패하는 규칙, MOLIT 검증 실패, billing key 덮어쓰기 방지 같은 세부 규칙은 unit test에서 검증한다.

API test에서는 해당 service가 예외를 던졌을 때 API layer가 올바른 HTTP 응답으로 변환하는지만 확인한다.

## 3. status code 구분

FastAPI에서 발생하는 HTTP 오류는 발생 지점에 따라 status code가 다르다.

```text
422  Pydantic request parsing 실패
400  service 계층 ValueError를 exception handler가 변환한 비즈니스 오류
401  인증 토큰 없음 또는 토큰 검증 실패
403  인증은 됐지만 권한 없음
404  resource를 찾을 수 없는 경우
```

필드 누락, 타입 오류처럼 Pydantic이 request body를 파싱하지 못하는 경우는 `422`로 검증한다.

service 계층에서 발생한 `ValueError`를 API exception handler가 변환한 경우는 `400`으로 검증한다.

어떤 조건에서 service가 실패하는지는 unit test에서 검증하고, API test에서는 HTTP 변환만 검증한다.

## 4. 사전 조건: API 레이어 구조

API 테스트를 작성하려면 아래 구조가 먼저 갖춰져 있어야 한다.

```text
app/
  main.py
  api/
    deps.py
    routes/
      auth.py
      card.py
      parking.py
      payment.py
```

`app/main.py`에는 FastAPI app 인스턴스가 있어야 한다.

`app/api/deps.py`에는 service와 auth dependency를 주입하는 함수가 있어야 한다.

현재 레포에 위 파일들이 없다면 API 테스트 작성 전에 API 레이어 구조를 먼저 만들기로 팀에서 합의한다.

이 문서의 예시 코드는 위 구조가 갖춰진 상태를 기준으로 한다.

## 5. TestClient 설정

API test는 FastAPI `TestClient`를 사용한다.

```python
from fastapi.testclient import TestClient
from app.main import app
```

`TestClient`는 fixture로 만들어 재사용한다.

```python
@pytest.fixture
def api_client():
    with TestClient(app) as client:
        yield client
```

API test에서는 실제 DB, Redis, 외부 client를 사용하지 않는다.

대신 `app.dependency_overrides`로 service dependency를 stub으로 교체한다.

## 6. 테스트 파일 구조

API 테스트 파일은 아래 순서로 작성한다.

```text
1. 파일 docstring
2. import
3. 테스트 상수
4. Stub 클래스
5. pytest fixture
6. 테스트 클래스
7. 테스트 함수
```

예:

```python
"""
카드 등록 / Billing Key API 테스트
UC-CARD-001: POST /card/order
UC-CARD-002: POST /card/webhook
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


VALID_CAR_ID = "car-001"
VALID_ORDER_ID = "order-abc-001"
VALID_PG_URL = "https://mock-pg.test/card-register?order_id=order-abc-001"
VALID_BILLING_KEY = "bk-xyz-9999"
VALID_SIGNATURE = "valid-hmac-signature"
```

## 7. Stub 클래스 작성 규칙

API test에서는 service 계층을 stub으로 교체해서 HTTP 계층만 검증한다.

Stub 클래스는 성공 또는 실패를 반환하는 최소 구현만 작성한다. 비즈니스 로직을 포함하지 않는다.

예:

```python
from app.application.card.create_card_order import CreateCardOrderResult


class StubCreateCardOrderService:
    def execute(self, command):
        return CreateCardOrderResult(
            order_id=VALID_ORDER_ID,
            pg_url=VALID_PG_URL,
        )
```

실패 케이스를 검증할 때는 service가 예외를 던지는 Stub을 별도로 만든다.

```python
class StubCreateCardOrderServiceThatFails:
    def execute(self, command):
        raise ValueError("vehicle_not_found")
```

Stub 안에서 request 값을 다시 검증하거나 복잡한 분기 처리를 넣지 않는다.

## 8. dependency_overrides 작성 규칙

API test에서는 `app.dependency_overrides`로 dependency를 교체한다.

`dependency_overrides.clear()`를 직접 호출하지 않는다. 다른 테스트의 override까지 지울 수 있기 때문이다.

대신 기존 override를 백업하고 테스트가 끝난 뒤 복구한다.

```python
from app.api.deps import get_create_card_order_service


@pytest.fixture
def api_client_with_service_stub():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_create_card_order_service] = (
        lambda: StubCreateCardOrderService()
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides = original
```

fixture 이름에는 어떤 dependency가 override되는지 드러나게 작성한다.

예:

```text
api_client_with_service_stub
api_client_authenticated
api_client_with_failing_service_stub
```

## 9. 인증 guard 테스트

인증이 필요한 endpoint는 성공 경로와 인증 실패 경로를 분리해서 검증한다.

성공 경로에서는 auth dependency도 override해서 인증을 통과시킨다.

```python
from app.api.deps import get_current_user


def fake_current_user():
    return {"user_id": "user-001"}


@pytest.fixture
def api_client_authenticated():
    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_create_card_order_service] = (
        lambda: StubCreateCardOrderService()
    )
    app.dependency_overrides[get_current_user] = fake_current_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides = original
```

401 검증에서는 auth dependency를 override하지 않는다. 토큰 없이 호출해서 실제 auth guard가 동작하는지 확인한다.

```python
def test_unauthenticated_request_returns_401(self, api_client_with_service_stub):
    response = api_client_with_service_stub.post(
        "/card/order",
        json={
            "car_id": VALID_CAR_ID,
            "plate": "12가3456",
            "bank_name": "신한은행",
            "agree_terms": True,
        },
    )

    assert response.status_code == 401
```

인증 토큰 자체의 발급 로직은 API test에서 검증하지 않는다. 그것은 UC-AUTH unit test 또는 별도 auth API test의 책임이다.

## 10. 테스트 클래스와 함수명

테스트 클래스 이름은 API 유스케이스 이름에 맞춘다.

테스트 클래스 docstring에는 UC 번호와 API 경로를 적는다.

```python
class TestCreateCardOrderApi:
    """UC-CARD-001 - POST /card/order"""
```

테스트 함수명은 영어 snake_case를 사용한다.

```python
def test_valid_request_returns_200_with_pg_url(...):
    ...

def test_missing_car_id_returns_422(...):
    ...

def test_unauthenticated_request_returns_401(...):
    ...
```

하나의 테스트 함수는 하나의 HTTP 계약만 검증한다.

좋은 예:

```text
정상 요청이면 200과 pg_url을 반환한다
필수 필드가 누락되면 422를 반환한다
인증 토큰이 없으면 401을 반환한다
service 예외가 발생하면 400을 반환한다
```

나쁜 예:

```text
성공 응답, 인증 실패, request validation을 한 테스트에 모두 섞는다
unit test에서 검증한 비즈니스 분기를 API test에서 반복한다
```

## 11. 성공 케이스 작성 규칙

정상 요청에서는 아래 항목을 검증한다.

```text
HTTP status code
response body의 핵심 필드 존재 여부
response body의 핵심 필드 값
```

예:

```python
def test_valid_request_returns_200_with_pg_url(self, api_client_authenticated):
    response = api_client_authenticated.post(
        "/card/order",
        json={
            "car_id": VALID_CAR_ID,
            "plate": "12가3456",
            "bank_name": "신한은행",
            "agree_terms": True,
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert "order_id" in body
    assert "pg_url" in body
    assert body["order_id"] == VALID_ORDER_ID
```

response body의 모든 필드를 전수 검증하지 않는다. OpenAPI 스키마에서 필수로 정의한 핵심 필드 위주로 확인한다.

## 12. Request validation 케이스 작성 규칙

Pydantic이 파싱할 수 없는 요청은 `422`를 반환하는지 확인한다.

대표적인 경우:

```text
필수 필드 누락
타입 오류
enum 값 오류
body 형식 오류
```

예:

```python
def test_missing_car_id_returns_422(self, api_client_authenticated):
    response = api_client_authenticated.post(
        "/card/order",
        json={
            "plate": "12가3456",
            "bank_name": "신한은행",
            "agree_terms": True,
        },
    )

    assert response.status_code == 422
```

필드 누락과 타입 오류를 모두 같은 파일에서 과도하게 반복하지 않는다. endpoint별 핵심 request validation만 최소로 확인한다.

## 13. 비즈니스 오류 케이스 작성 규칙

service stub이 `ValueError`를 던질 때 API layer가 `400`으로 변환하는지 확인한다.

```python
def test_service_error_returns_400(
    self,
    api_client_authenticated_with_failing_service_stub,
):
    response = api_client_authenticated_with_failing_service_stub.post(
        "/card/order",
        json={
            "car_id": VALID_CAR_ID,
            "plate": "12가3456",
            "bank_name": "신한은행",
            "agree_terms": True,
        },
    )

    assert response.status_code == 400
```

어떤 입력에서 `ValueError`가 발생해야 하는지는 unit test에서 검증한다.

API test에서는 exception handler가 HTTP 응답으로 변환하는지만 확인한다.

## 14. 외부 호출 endpoint 테스트

외부 시스템이 직접 호출하는 endpoint는 app access token 대신 signature 또는 커스텀 헤더 기반 계약을 검증한다.

예:

```text
PG webhook
PMS entry webhook
PMS payment complete webhook
```

외부 호출 endpoint는 인증 방식이 다르므로 `auth_headers` fixture를 사용하지 않는다.

signature나 커스텀 헤더가 보안 경계 역할을 하므로 API test에서 반드시 확인한다.

예:

```python
def test_valid_webhook_returns_200(self, api_client_with_service_stub):
    response = api_client_with_service_stub.post(
        "/card/webhook",
        json={
            "order_id": VALID_ORDER_ID,
            "billing_key": VALID_BILLING_KEY,
            "card_last_four": "1234",
            "status": "active",
            "signature": VALID_SIGNATURE,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_invalid_signature_returns_400(
    self,
    api_client_with_failing_service_stub,
):
    response = api_client_with_failing_service_stub.post(
        "/card/webhook",
        json={
            "order_id": VALID_ORDER_ID,
            "billing_key": VALID_BILLING_KEY,
            "card_last_four": "1234",
            "status": "active",
            "signature": "tampered",
        },
    )

    assert response.status_code == 400
```

## 15. 기준 문서

API test는 아래 문서를 기준으로 작성한다.

```text
docs/api/car-pay-in-openapi.yaml
docs/use-cases/
```

endpoint 경로, request body, response body, status code는 OpenAPI 문서를 우선한다.

성공 흐름과 실패 흐름은 use-case 문서를 함께 확인한다.

테스트 파일에 남아 있는 오래된 경로나 스키마는 기준으로 삼지 않는다.

## 16. 최종 원칙

API test는 HTTP 계약을 검증한다.

비즈니스 규칙은 unit test에서 검증한다.

API test에서는 실제 DB, Redis, 외부 API를 사용하지 않는다.

service dependency는 stub으로 교체한다.

auth guard, request validation, response schema, status code는 API test에서 검증한다.

Pydantic 파싱 실패는 `422`로 검증한다.

service 예외의 HTTP 변환은 `400`, `401`, `403`, `404` 등 API layer의 책임으로 검증한다.

`dependency_overrides.clear()` 대신 기존 override를 백업하고 복구한다.

OpenAPI 스펙과 use-case 문서를 항상 기준으로 삼는다.
