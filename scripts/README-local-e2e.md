# Local E2E Start Scripts

Use these from the repository root on Windows:

```bat
scripts\start-local-e2e.bat
```

This starts:

- Docker Compose services: backend, Postgres DBs, Redis, PMS, Mock PG, Mock Card
- ngrok tunnel to backend port `8000`
- Android local API values in `services/android-app/local.properties`

Before real Hyundai OAuth:

1. Copy `.env.example` to `.env` if the script has not created it.
2. Fill `HYUNDAI_CLIENT_ID` and `HYUNDAI_CLIENT_SECRET`. The start script and backend will stop if these are blank or still placeholders.
3. Set `PUBLIC_BASE_URL` to the exact ngrok URL registered in Hyundai developer center.
4. Hyundai URLs must match:
   - Account redirect: `{PUBLIC_BASE_URL}/auth/redirect`
   - Data agreement redirect: `{PUBLIC_BASE_URL}/auth/data-agreement/redirect`
   - Data callback: `{PUBLIC_BASE_URL}/data/callback`

For Android emulator card registration, keep `PG_PUBLIC_BASE_URL=http://10.0.2.2:8002`.
For a physical device or AWS deployment, set `PG_PUBLIC_BASE_URL` to a URL the device can open.
Local E2E sets `MOLIT_VERIFY_ENABLED=false` because this compose stack does not include a MOLIT mock service.
It also keeps `MOCK_PG_ALLOW_FAKE_CARD_ON_VERIFY_FAILURE=true` so demo card registration can complete even when you type arbitrary test values into the Mock PG WebView.

If `ngrok.exe` is not on PATH, set this once in Command Prompt:

```bat
set NGROK_EXE=C:\path\to\ngrok.exe
```

To stop:

```bat
scripts\stop-local-e2e.bat
```

To stop containers without killing ngrok:

```bat
scripts\stop-local-e2e.bat -KeepNgrok
```
