# 🚘 CarPayIn — AAOS 차량 자동 결제 플랫폼

> 현대오토에버 모빌리티 SW 스쿨 3기 팀 프로젝트 (5인)  
> 2026.04 ~ 2026.06

AAOS 탑재 차량이 주차장 진입부터 요금 결제·출차까지 사용자 개입 없이 자동으로 처리하는 차량 결제 시스템입니다.

---

## 🏗️ Architecture

<img width="1032" height="727" alt="Group 417 white" src="https://github.com/user-attachments/assets/1576426e-dd93-480d-abb0-5c17f60241ce" />

---

## 📦 서비스 구성

| 서비스 | 역할 | 인프라 |
|---|---|---|
| carpayin-backend | 핵심 비즈니스 로직 (인증·카드·주차·결제) | ECS Fargate, RDS PostgreSQL Multi-AZ, ElastiCache Redis |
| mock-pms | 주차관제 시스템 (입차 이벤트, 요금 계산) | EC2 + Docker Compose + PostgreSQL |
| mock-pg | 결제 게이트웨이 (billing key 발급, 승인) | EC2 + Docker Compose + PostgreSQL |
| mock-card | 카드사 (카드 검증, card_token 발급) | OpenStack k3s, WireGuard VPN + PostgreSQL |
| android-app | AAOS 탑재 Android 클라이언트 | Kotlin / Pleos |

```
CarPayIn
├── services
│   ├── android-app/        AAOS 차량 앱 (로컬/차량 내 테스트용)
│   ├── carpayin-backend/   인증·차량·카드·주차·결제 메인 API
│   ├── mock-card/          카드사 Mock API
│   ├── mock-pg/            PG Mock API + 카드 등록 WebView
│   ├── pms/                주차관제 시스템 Mock API
│   └── webots/             Webots 차량/차단기 시뮬레이션 컨트롤러
├── docs
│   ├── api/                OpenAPI 계약서
│   ├── DB schemas/         DB·Redis 스키마 문서
│   ├── deployment/         레지스트리·CI/CD·배포 노트
│   ├── diagrams/           Mermaid 시퀀스 다이어그램
│   ├── scenarios/          시나리오 플로우 문서
│   └── use-cases/          유스케이스 명세
└── scripts
    ├── build-push-images.ps1      로컬 GitLab Registry 이미지 빌드/푸시
    ├── start-local-full.ps1       Docker 서비스 + 로컬 지원 구성 기동
    ├── deploy-from-registry.ps1   레지스트리 이미지 pull 후 Docker Compose 실행
    ├── start-local-e2e.ps1        로컬 E2E 의존성 기동
    └── stop-local-e2e.ps1         로컬 E2E 의존성 종료
```

---

## 🛠️ Tech Stack

<p>
<img src="https://img.shields.io/badge/amazonaws-232F3E?style=flat-square&logo=amazonaws&logoColor=white">
<img src="https://img.shields.io/badge/terraform-7B42BC?style=flat-square&logo=terraform&logoColor=white">
<img src="https://img.shields.io/badge/docker-2496ED?style=flat-square&logo=docker&logoColor=white">
<img src="https://img.shields.io/badge/prometheus-E6522C?style=flat-square&logo=prometheus&logoColor=white">
<img src="https://img.shields.io/badge/grafana-F46800?style=flat-square&logo=grafana&logoColor=white">
<img src="https://img.shields.io/badge/postgresql-4169E1?style=flat-square&logo=postgresql&logoColor=white">
<img src="https://img.shields.io/badge/redis-DC382D?style=flat-square&logo=redis&logoColor=white">
<img src="https://img.shields.io/badge/python-3776AB?style=flat-square&logo=python&logoColor=white">
</p>

---

## ⚙️ 로컬 환경 설정

`.env.example`을 `.env`로 복사 후 아래 값 입력:

```
PUBLIC_BASE_URL
HYUNDAI_CLIENT_ID
HYUNDAI_CLIENT_SECRET
PG_PUBLIC_BASE_URL
```

---

## 🚀 로컬 실행

```bash
docker compose up -d --build
```

| 서비스 | 포트 | Swagger |
|---|---|---|
| carpayin-backend | 8000 | http://localhost:8000/docs |
| pms | 8001 | http://localhost:8001/docs |
| mock-pg | 8002 | http://localhost:8002/docs |
| mock-card | 8003 | http://localhost:8003/docs |

---

## 🧪 테스트

```bash
# 전체 테스트
make test

# 서비스별 테스트
cd services/carpayin-backend
python -m pytest tests/unit tests/api -q --import-mode=importlib
```

---

## 🔄 CI/CD

시맨틱 버전 태그 push 시 GitLab Registry에 이미지 자동 빌드·푸시:

```bash
git tag 0.0.2
git push origin 0.0.2
```
