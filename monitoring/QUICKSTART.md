# CarPayIn 모니터링 빠른 시작

## 전제 조건

- AWS CLI + Session Manager Plugin 설치
- Docker Desktop 실행 중

---

## 1단계: 터널 열기 (터미널 4개)

**터미널 1 — MockPG DB (SSM)**
`aws ssm start-session --target i-048afd36c81cd672d --document-name AWS-StartPortForwardingSession --parameters portNumber=5432,localPortNumber=15433 --profile carpayin`

**터미널 2 — MockPMS DB (SSM)**
`aws ssm start-session --target i-0dcfbe5685b79ac7d --document-name AWS-StartPortForwardingSession --parameters portNumber=5432,localPortNumber=15435 --profile carpayin`

**터미널 3 — MockCard DB (SSH 터널, OpenStack)**
`ssh -L 15434:10.0.2.208:5432 -p 40001 ubuntu@112.218.95.58 -N`

**터미널 4 — CarPayIn Redis (SSM, GitLab Runner 경유)**
`aws ssm start-session --target i-0f723f759fe776097 --document-name AWS-StartPortForwardingSessionToRemoteHost --parameters "host=carpayin-redis-vkjvvb.serverless.apn2.cache.amazonaws.com,portNumber=6379,localPortNumber=16379" --profile carpayin`

---

## 2단계: 환경변수 설정

`Copy-Item .env.example .env`

모든 값이 이미 채워져 있습니다. 별도 수정 불필요.

---

## 3단계: 모니터링 스택 시작

`docker compose up -d --build`

---

## 4단계: Grafana 접속

`http://localhost:3000` → admin / carpayin123

---

## 포트 정보

| 서비스 | 포트 |
|---|---|
| Grafana | 3000 |
| Prometheus | 9090 |
| DB Exporter | 9001 |
| Redis Exporter (carpayin) | 9121 |
| SSM 터널 MockPG | 15433 |
| SSM 터널 MockPMS | 15435 |
| SSH 터널 MockCard | 15434 |
| SSM 터널 Redis | 16379 |

---

## 스택 종료

`docker compose down`

터미널 4개의 터널도 `Ctrl+C` 로 종료하세요.
