# 06. 결제 완료 알림 Outbox / SQS / Lambda / IoT Core

## 목적

결제 성공 후 앱에 결제 완료 알림을 보내야 하지만, 알림 발송은 결제 자체보다 실패 가능성이 높다.
따라서 결제 성공 기록과 알림 발송 대상 이벤트를 Car Pay-in DB에 먼저 저장하고, Amazon SQS, Lambda, AWS IoT Core는 그 이후 전달 경로로 사용한다.

## 참여 컴포넌트

- Car Pay-in Backend
- Car Pay-in DB
- Amazon SQS
- Payment Notification Lambda
- AWS IoT Core
- AAOS App

## 핵심 데이터

- `transactions`: 결제 성공/실패의 기준 기록
- `payment_notification_outbox`: 앱에 보내야 할 결제 완료 알림 이벤트 기록

## 흐름

1. 사용자가 `/payment`를 호출하고 Mock PG 결제가 성공한다.
2. Backend는 `transactions` row를 `success`로 갱신한다.
3. Backend는 같은 결제 성공 처리에서 `payment_notification_outbox`에 `payment.completed` 이벤트를 `pending` 상태로 저장한다.
4. Backend는 사용자에게 결제 성공 응답을 반환한다.
5. 알림 worker는 `payment_notification_outbox`에서 `pending`이고 `next_attempt_at <= now()`인 이벤트를 조회한다.
6. worker는 이벤트 상태를 `publishing`으로 변경한다.
7. worker 또는 backend publisher는 SQS에 `payment.completed` 이벤트를 전송한다.
8. Lambda는 SQS 메시지를 받아 AWS IoT Core topic으로 publish한다.
9. 앱은 IoT Core를 통해 결제 완료 알림을 수신한다.
10. 발송 성공 시 outbox row를 `published` 또는 `delivered`로 갱신한다.
11. 발송 실패 시 `attempts`를 증가시키고 `next_attempt_at`을 뒤로 미뤄 재시도한다.
12. `max_attempts`를 초과하면 `dead` 상태로 둔다.

## 상태

- `pending`: 아직 발송하지 않은 이벤트
- `publishing`: worker가 처리 중인 이벤트
- `published`: SQS 전송 또는 IoT publish까지 성공한 이벤트
- `delivered`: 최종 전달 확인까지 성공한 이벤트
- `failed`: 재시도 가능한 실패 상태
- `dead`: 최대 재시도 횟수를 초과한 상태

## 이유

- SQS는 전달 큐이므로 영구적인 업무 기록의 기준으로 두지 않는다.
- 결제 성공과 알림 이벤트 생성을 DB에 함께 남기면, 결제는 성공했는데 알림 이벤트가 사라지는 상황을 줄일 수 있다.
- 알림 발송 실패가 있어도 결제 성공은 유지되고, outbox 기반으로 안전하게 재시도할 수 있다.
