# Webots Controllers

Webots-side helpers for the local parking simulation.

## Responsibilities

- Send simulated LPR entry events to PMS from `vehicle_controller.py`.
- Receive MQTT barrier commands from `barrier_controller.py`.
- Share local environment values through `shared_config.py`.
- Optionally proxy GPS/location updates with `gps_proxy.py`.

## Configuration

Controllers read root `.env` values through `shared_config.py` when available.
Useful local defaults:

```text
PARKING_PMS_URL=http://localhost:8001
MQTT_HOST=localhost
MQTT_PORT=1883
```

## Dependencies

Webots provides the `controller` module at runtime. Extra Python packages are
listed in `requirements.txt`:

```powershell
pip install -r services\webots\requirements.txt
```

## Local Flow

1. Start the root Docker Compose stack so PMS and MQTT are available.
2. Start the Webots world using these controller files.
3. `vehicle_controller.py` posts LPR entry events to PMS.
4. PMS/backend payment completion can publish MQTT commands that
   `barrier_controller.py` consumes.
