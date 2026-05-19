# 02. 차량 선택 / 차량 등록

관련 다이어그램: `docs/diagrams/lucid-02-vehicle-confirmation.mmd`

## 이 단계의 목적

현대 계정으로 확인된 사용자에게 어떤 차량들이 있는지 조회하고, 그중 Car Pay-in에 연결할 차량을 확정하는 단계다.

이 단계가 끝나면 Car Pay-in DB에 "이 사용자의 이 차량을 서비스에 등록했다"는 정보가 남는다. 다만 아직 결제수단은 연결되지 않았으므로 자동결제 가능 상태는 아니다.

## 등장하는 참여자

- AAOS App: 로그인 완료 여부를 polling하고, 사용자가 차량을 선택하게 한다.
- Car Pay-in Backend: 현대 Data API로 차량 목록을 조회하고, 선택된 차량을 DB에 저장한다.
- Redis: 현대 OAuth 결과와 앱에 내려줄 로그인 결과를 임시 저장한다.
- Hyundai Data API: 현대 계정에 등록된 차량 목록을 제공한다.
- Car Pay-in DB: 확정된 차량과 앱 refresh token을 저장한다.

## 핵심 개념

`hyundai_oauth:{session_id}`는 현대 OAuth와 Data API를 통해 얻은 결과를 잠깐 보관하는 Redis key다. 사용자 정보, 현대 token, 차량 목록 같은 원본 결과가 들어간다.

`app_login_result:{session_id}`는 AAOS 앱이 polling으로 가져갈 로그인 완료 결과다. 차량 확정용 임시 access token, 사용자 ID, 사용자 이름, 차량 목록이 들어간다.

`vehicles`는 실제 서비스에 등록된 차량 정보의 source of truth다. 사용자가 차량을 확정해야 이 테이블에 저장된다.

## 단계별 흐름

1. 백엔드는 현대 access token으로 Hyundai Data API에 차량 목록을 요청한다.
2. Hyundai Data API는 `car_id`, `car_sellname`, 모델명 등 사용자의 차량 목록을 반환한다.
3. 백엔드는 이 결과를 Redis의 `hyundai_oauth:{session_id}`에 임시 저장한다.
4. 백엔드는 차량 확정용 임시 access token을 발급하고, 앱이 polling으로 가져갈 결과를 `app_login_result:{session_id}`에 저장한다.
5. AAOS 앱은 QR 화면에서 주기적으로 `/auth/session/{session_id}/status`를 호출한다.
6. 아직 완료되지 않았으면 백엔드는 `pending` 또는 `agreement_required`를 반환한다.
7. 완료되면 백엔드는 차량 확정용 임시 access token과 차량 목록을 반환한다.
8. 차량이 1대면 앱은 자동으로 선택할 수 있고, 여러 대면 사용자가 직접 차량을 선택한다.
9. 앱은 `/auth/confirm-car`로 선택된 `car_id`를 백엔드에 보낸다.
10. 백엔드는 이 `car_id`가 현대 Data API에서 받은 차량 목록 안에 실제로 있는지 확인한다.
11. 검증이 통과하면 `vehicles` 테이블에 차량 정보를 저장하거나 갱신한다.
12. 앱 refresh token은 원문을 저장하지 않고 hash로 만들어 `app_refresh_tokens`에 저장한다.
13. 백엔드는 최종 앱 access token, refresh token과 함께 차량 확정 완료를 응답한다.

## 이 단계가 끝나면 남는 데이터

Redis:

- `hyundai_oauth:{session_id}`: 현대 OAuth/Data API 결과 임시 저장
- `app_login_result:{session_id}`: AAOS 앱 polling용 로그인 완료 결과

Car Pay-in DB:

- `vehicles`: 서비스에 등록된 차량 정보
- `app_refresh_tokens`: 앱 refresh token hash와 만료 정보

## 발표 멘트

두 번째 단계는 현대 계정에서 가져온 차량 목록 중 실제로 Car Pay-in에 연결할 차량을 확정하는 과정입니다. 백엔드는 현대 Data API로 차량 목록을 가져오고, 앱은 polling을 통해 로그인 완료 결과와 차량 목록을 받습니다. 사용자가 차량을 선택하면 백엔드는 그 차량이 현대 API 결과에 포함된 차량인지 검증한 뒤 `vehicles`에 저장합니다. 이 시점에는 차량 연동만 끝난 상태이고, 결제수단은 아직 연결되지 않았습니다.
