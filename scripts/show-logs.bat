@echo off
cd /d "%~dp0.."
start "Backend  :8000" cmd /k "docker compose logs -f carpayin-backend"
start "Mock-PMS :8001" cmd /k "docker compose logs -f pms"
start "Mock-PG  :8002" cmd /k "docker compose logs -f mock-pg"
start "Mock-Card:8003" cmd /k "docker compose logs -f mock-card"
start "MQTT     :1883" cmd /k "docker compose logs -f mqtt"
