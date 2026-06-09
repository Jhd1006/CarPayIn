# Android App

AAOS/Android client for the Car Pay In local and in-car parking payment flow.

## Responsibilities

- Create QR login sessions and poll login completion.
- Confirm a Hyundai vehicle and store app tokens locally.
- Start card registration through the mock PG WebView.
- Fetch partner parking lots and send parking pre-notifications.
- Receive parking/payment updates through MQTT.
- Keep local parking, token, and transaction state on the device.

## Structure

```text
app/src/main/java/com/example/carpayin/
  config/       BuildConfig-backed runtime values
  data/         Local token, parking, and transaction stores
  network/      Backend API and MQTT clients
  service/      Foreground service for parking/MQTT state
  ui/           Main, registration, card registration, and dev UI
  vehicle/      Vehicle, geofence, and navigation helpers

app/src/main/res/
  drawable*/    UI backgrounds, launcher assets, and card logos
  layout/       XML layouts
  values/       Colors, strings, and themes
```

## Local Configuration

Copy `local.properties.example` to `local.properties`:

```powershell
Copy-Item services\android-app\local.properties.example services\android-app\local.properties
```

Local emulator defaults:

```text
CARPAYIN_BACKEND_BASE_URL=http://10.0.2.2:8000
CARPAYIN_QR_BASE_URL=https://your-ngrok-domain.ngrok-free.app
CARPAYIN_MQTT_BROKER_URL=tcp://10.0.2.2:1883
CARPAYIN_EMULATOR_LOCALHOST_REWRITE=true
```

Use a public URL such as ngrok for `CARPAYIN_QR_BASE_URL` when a phone browser
or Hyundai OAuth callback must reach the backend.

## Build

Compile the debug Kotlin sources:

```powershell
cd services\android-app
.\gradlew.bat :app:compileDebugKotlin
```

Run unit tests:

```powershell
cd services\android-app
.\gradlew.bat testDebugUnitTest
```

## Backend Contract

The app currently uses these backend endpoints:

- `POST /auth/qr-session`
- `GET /auth/session/{session_id}/status`
- `POST /auth/confirm-car`
- `POST /auth/refresh`
- `POST /card/order`
- `GET /parking/lots`
- `POST /pre-notify`
- `GET /fee/{session_id}`
- `POST /payment`

`ApiManager.unregister()` is a best-effort cleanup call during local reset.
The current backend does not expose `POST /auth/unregister`, so local session
clear remains the real cleanup path until that API is implemented.

The shared OpenAPI contract lives at `../../docs/api/car-pay-in-openapi.yaml`.

## Local Flow

1. Start the root Docker Compose stack.
2. Set `PUBLIC_BASE_URL` and Android `CARPAYIN_QR_BASE_URL` to the public URL
   that can receive the OAuth callback.
3. Compile and launch the Android app.
4. Start registration, scan or open the QR URL, finish Hyundai OAuth, and let
   the app poll `/auth/session/{session_id}/status`.
5. Confirm a vehicle, register a card, then use navigation/geofence flows to
   trigger `/pre-notify` and payment.

## Generated Files

Do not commit local screenshots, view hierarchy dumps, `.gradle/`, build
outputs, or `local.properties`. The root-level Android screenshots and dump XML
files are intentionally ignored.
