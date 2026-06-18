# AWS Environment Variables

이 문서는 AWS 배포 시 코드 수정 없이 환경별 주소와 시크릿을 바꾸기 위해 필요한 환경변수를 정리한다.

공통 원칙:

- AWS 배포 환경에서는 `APP_ENV=aws`를 설정한다.
- `APP_ENV=aws`에서는 주요 DB URL, 외부 API URL, 웹훅 시크릿이 없으면 앱 시작 시 실패한다.
- 실제 시크릿은 Git 저장소에 넣지 않고 ECS task env/secret, EC2 env file, SSM Parameter Store, Secrets Manager, Vault 중 하나로 관리한다.
- URL 값은 마지막 `/` 없이 넣는 것을 권장한다.

## carpayin-backend

ECS task definition에 넣을 값이다.

```text
APP_ENV=aws

DATABASE_URL=postgresql+psycopg://<user>:<password>@<carpayin-db-host>:5432/<db>
REDIS_URL=redis://<redis-host>:6379/0

PUBLIC_BASE_URL=https://<carpayin-backend-alb-or-domain>
PG_BASE_URL=https://<mock-pg-alb-or-domain>
PG_PUBLIC_BASE_URL=https://<mock-pg-alb-or-domain>
PMS_BASE_URL=https://<pms-alb-or-domain>

AWS_REGION=ap-northeast-2
SQS_NOTIFICATION_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/<account-id>/<payment-notification-queue>
SQS_NOTIFICATION_PUBLISH_ENABLED=true

APP_TOKEN_SECRET=<long-random-secret>
APP_REFRESH_TOKEN_HASH_SECRET=<long-random-secret-optional>
HYUNDAI_TOKEN_ENCRYPTION_SECRET=<long-random-secret>
PG_WEBHOOK_SECRET=<shared-secret-with-mock-pg>
PMS_WEBHOOK_SECRET=<shared-secret-with-pms>

HYUNDAI_CLIENT_ID=<hyundai-client-id>
HYUNDAI_CLIENT_SECRET=<hyundai-client-secret>
HYUNDAI_AUTHORIZE_URL=https://prd.kr-ccapi.hyundai.com/api/v1/user/oauth2/authorize
HYUNDAI_TOKEN_URL=https://prd.kr-ccapi.hyundai.com/api/v1/user/oauth2/token
HYUNDAI_USER_INFO_URL=https://prd.kr-ccapi.hyundai.com/api/v1/user/profile
HYUNDAI_VEHICLE_LIST_URL=https://dev.kr-ccapi.hyundai.com/api/v1/car/profile/carlist

MOLIT_VERIFY_ENABLED=false
MOLIT_BASE_URL=<molit-api-base-url-if-enabled>
MOLIT_API_KEY=<molit-api-key-if-enabled>
```

## payment-notification-lambda

SQS 메시지를 받아 AWS IoT Core topic으로 publish하는 Lambda에 넣을 값이다.

```text
APP_ENV=aws
AWS_REGION=ap-northeast-2
AWS_IOT_ENDPOINT=<aws-iot-data-endpoint>
SQS_NOTIFICATION_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/<account-id>/<payment-notification-queue>
```

## mock-pg

Mock PG EC2 또는 컨테이너 실행 환경에 넣을 값이다.

```text
APP_ENV=aws

MOCK_PG_DATABASE_URL=postgresql+psycopg://<user>:<password>@<mock-pg-db-host>:5432/<db>
MOCK_CARD_BASE_URL=https://<mock-card-api-domain>
CARPAYIN_BACKEND_BASE_URL=https://<carpayin-backend-alb-or-domain>
PG_WEBHOOK_SECRET=<shared-secret-with-carpayin-backend>
MOCK_PG_ALLOW_FAKE_CARD_ON_VERIFY_FAILURE=false
```

로컬 데모에서는 `MOCK_PG_ALLOW_FAKE_CARD_ON_VERIFY_FAILURE=true`를 사용할 수 있지만, AWS 시연 환경에서는 가능하면 `false`를 권장한다.

## pms

PMS EC2 또는 컨테이너 실행 환경에 넣을 값이다.

```text
APP_ENV=aws

PMS_DATABASE_URL=postgresql+psycopg://<user>:<password>@<pms-db-host>:5432/<db>
CARPAYIN_BACKEND_BASE_URL=https://<carpayin-backend-alb-or-domain>
PMS_WEBHOOK_SECRET=<shared-secret-with-carpayin-backend>
PMS_FEE_PER_30_MINUTES=500
```

## Android

Android 앱은 `services/android-app/local.properties`에 값을 넣거나 Gradle property/환경변수로 주입할 수 있다. `build.gradle.kts`의 `localConfig()` 함수가 순서대로 local.properties → Gradle property → 환경변수를 탐색한다.

로컬 에뮬레이터 (`local` flavor):

```text
# services/android-app/local.properties
CARPAYIN_QR_BASE_URL=https://<ngrok-or-public-backend-url>
# IOT_ENDPOINT, COGNITO_IDENTITY_POOL_ID 미설정 시 IoT Core 연결 생략
```

AWS/실기기 (`aws` flavor):

```text
# services/android-app/local.properties (빌드 환경에만 존재, 커밋하지 않음)
CARPAYIN_BACKEND_BASE_URL=https://<carpayin-backend-alb-or-domain>
CARPAYIN_QR_BASE_URL=https://<carpayin-backend-alb-or-domain>
IOT_ENDPOINT=<aws-iot-data-endpoint>.iot.ap-northeast-2.amazonaws.com
COGNITO_IDENTITY_POOL_ID=ap-northeast-2:<cognito-identity-pool-id>
```

## Local Docker Compose

로컬 실행은 루트의 `.env.example`을 `.env`로 복사해서 사용한다.

```bash
cp .env.example .env
```

AWS 배포 값은 `.env`에 커밋하지 않는다.
