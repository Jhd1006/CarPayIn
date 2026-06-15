# 01. QR 로그인 / 현대 OAuth

관련 다이어그램: `docs/diagrams/01-qr-oauth-login.mmd`

## 이 단계의 목적

사용자가 차량에서 Car Pay-in 등록을 시작했을 때, 스마트폰의 MyHyundai 로그인을 통해 "이 사용자가 누구인지" 확인하는 단계다.

차량 안의 AAOS 앱은 직접 현대 로그인을 처리하지 않는다. 대신 앱이 QR을 보여주고, 사용자가 스마트폰으로 QR을 스캔해서 MyHyundai OAuth 로그인을 진행한다.

## 등장하는 참여자

- 사용자: 차량 등록을 시작하고 스마트폰으로 QR을 스캔한다.
- AAOS App: `session_id`와 `vin_hash`를 만들고 QR을 표시한다.
- 스마트폰 브라우저: QR URL을 열고 MyHyundai 로그인으로 이동한다.
- Car Pay-in Backend: QR 세션을 만들고 현대 OAuth 요청을 시작한다.
- Redis: QR 로그인 상태와 OAuth state 매핑을 임시 저장한다.
- MyHyundai OAuth API: 사용자 로그인과 authorization code 발급을 담당한다.
- Car Pay-in DB: 현대 사용자 정보를 저장한다. 현대 토큰은 저장하지 않는다.

## 핵심 개념

`session_id`는 AAOS 앱이 만든 QR 로그인 세션 ID다. 앱과 백엔드가 "지금 차량에서 시작된 이 로그인 요청"을 추적하기 위해 사용한다.

`vin_hash`는 차량 VIN 원문을 직접 노출하지 않기 위해 만든 해시값이다. 앱은 `sha256(VIN + session_id)`로 해싱한다. `session_id`를 함께 섞어 해싱하기 때문에 세션마다 다른 값이 나와 재사용 공격을 차단한다. `vin_hash`는 QR URL에 포함하지 않는다. QR 코드는 공개된 값이므로 노출되면 안 되고, QR 세션 생성 시점에 이미 백엔드 Redis에 저장해두기 때문에 URL에 실을 필요가 없다.

`oauth_state`는 백엔드가 새로 만든 일회용 랜덤값이다. 현대 OAuth URL의 `state` 파라미터에는 내부 `session_id`를 그대로 넣지 않고, `oauth_state`만 넣는다. 백엔드는 Redis에 `oauth_state -> session_id` 매핑을 저장해두고, 현대 callback이 돌아오면 이 값을 조회해서 원래 QR 세션을 찾는다.

## 단계별 흐름

1. 사용자가 AAOS 앱에서 차량 등록을 시작한다.
2. 앱은 `session_id`를 만들고, VHAL에서 읽은 차량 VIN으로 `vin_hash = sha256(VIN + session_id)`를 만든다.
3. 앱은 `POST /auth/qr-session { session_id, vin_hash }`를 백엔드에 보낸다.
4. 백엔드는 Redis에 `qr_session:{session_id}`를 저장한다.

```json
{
  "vin_hash": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

5. 백엔드는 다음 형태의 `login_url`을 앱에 반환한다.

```text
/auth/hyundai/start?session_id={session_id}
```

6. 앱은 이 URL을 QR 코드로 인코딩해 화면에 표시한다. QR URL에는 `vin_hash`를 포함하지 않는다.
7. 사용자가 스마트폰으로 QR을 스캔하면 스마트폰 브라우저가 백엔드의 `/auth/hyundai/start`로 들어온다.
8. 백엔드는 `oauth_state`라는 별도 랜덤값을 만들고 Redis에 `oauth_state:{oauth_state}`를 저장한다.

```json
{
  "session_id": "...",
  "status": "pending",
  "created_at": "...",
  "expires_at": "..."
}
```

9. 백엔드는 현대 OAuth 로그인 URL로 사용자를 redirect한다. 이때 현대에 넘기는 `state` 값은 `session_id`가 아니라 `oauth_state`다.
10. 사용자가 MyHyundai 로그인을 완료하면 현대 OAuth API가 백엔드 callback으로 authorization code와 state를 돌려준다.
11. 백엔드는 state 값으로 Redis의 `oauth_state`를 조회해서 원래 `session_id`를 찾는다.
12. 백엔드는 authorization code를 현대 token API에 보내 현대 access token과 refresh token을 받는다.
13. 백엔드는 현대 access token으로 사용자 정보와 차량 목록을 즉시 조회한다.
14. 백엔드는 현대 사용자 정보를 `users`에 저장하거나 갱신한다. 현대 access/refresh token은 이 시점 이후 사용되지 않으므로 저장하지 않는다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `qr_session:{session_id}`: QR 로그인 진행 상태와 `vin_hash`
- `oauth_state:{oauth_state}`: 현대 OAuth callback을 원래 `session_id`에 연결하기 위한 매핑
- `hyundai_oauth:{session_id}`: 차량 확정 전 임시 결과 (사용자 정보, 차량 목록, temp_access_token)
- `app_login_result:{session_id}`: AAOS 앱 polling용 로그인 완료 결과

Car Pay-in DB:

- `users`: 현대 로그인 기준 사용자 정보

## 발표 멘트

첫 번째 단계는 차량에서 시작된 QR 로그인 요청을 스마트폰의 현대 OAuth 로그인과 연결하는 과정입니다. 앱은 `session_id`와 `vin_hash`를 만들고, QR을 표시하기 전에 먼저 백엔드에 `vin_hash`를 전송해 Redis에 저장합니다. QR URL에는 `session_id`만 담아 공개 노출을 최소화합니다. 백엔드는 Redis의 `qr_session`에 `vin_hash`를 저장한 뒤, 현대 OAuth로 이동할 때는 내부 `session_id`를 직접 넘기지 않고 일회용 `oauth_state`를 사용합니다. OAuth callback이 돌아오면 백엔드는 현대 토큰으로 사용자 정보와 차량 목록을 동기 조회하고 즉시 버립니다. 사용자 정보는 DB에 저장하고, 차량 목록과 임시 token은 Redis에 보관해 앱이 polling으로 확인할 수 있게 합니다.
