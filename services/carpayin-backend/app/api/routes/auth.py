from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse

from app.api.deps import (
    get_confirm_vehicle_service,
    get_create_qr_session_service,
    get_handle_hyundai_oauth_callback_service,
    get_login_session_status_service,
    get_refresh_access_token_service,
    get_start_hyundai_oauth_service,
)
from app.api.schemas.auth import (
    ConfirmVehicleRequest,
    ConfirmVehicleResponse,
    HyundaiOAuthCallbackResponse,
    QrSessionCreateRequest,
    QrSessionCreateResponse,
    RefreshAccessTokenRequest,
    RefreshAccessTokenResponse,
    SessionStatusResponse,
)
from app.application.auth.confirm_vehicle import (
    ConfirmVehicleCommand,
    ConfirmVehicleService,
)
from app.application.auth.create_qr_session import (
    CreateQrSessionCommand,
    CreateQrSessionService,
)
from app.application.auth.get_login_session_status import (
    GetLoginSessionStatusCommand,
    GetLoginSessionStatusService,
)
from app.application.auth.handle_hyundai_oauth_callback import (
    HandleHyundaiOAuthCallbackCommand,
    HandleHyundaiOAuthCallbackService,
)
from app.application.auth.refresh_access_token import (
    RefreshAccessTokenCommand,
    RefreshAccessTokenService,
)
from app.application.auth.start_hyundai_oauth import (
    StartHyundaiOAuthCommand,
    StartHyundaiOAuthService,
)


router = APIRouter(prefix="/auth", tags=["Auth"])


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "missing_bearer_token",
            },
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHORIZED",
                "message": "missing_bearer_token",
            },
        )
    return token


@router.post("/qr-session", response_model=QrSessionCreateResponse)
def create_qr_session(
    request: QrSessionCreateRequest,
    service: CreateQrSessionService = Depends(get_create_qr_session_service),
) -> QrSessionCreateResponse:
    result = service.execute(
        CreateQrSessionCommand(
            login_session_id=request.login_session_id,
            vin_hash=request.vin_hash,
        )
    )

    return QrSessionCreateResponse(login_url=result.login_url)


@router.get("/hyundai/start", status_code=302)
def start_hyundai_oauth(
    session_id: str,
    service: StartHyundaiOAuthService = Depends(get_start_hyundai_oauth_service),
) -> RedirectResponse:
    result = service.execute(StartHyundaiOAuthCommand(session_id=session_id))
    return RedirectResponse(url=result.redirect_url, status_code=302)


@router.get("/redirect", response_model=HyundaiOAuthCallbackResponse)
def handle_hyundai_oauth_callback(
    code: str,
    state: str,
    service: HandleHyundaiOAuthCallbackService = Depends(
        get_handle_hyundai_oauth_callback_service,
    ),
) -> HyundaiOAuthCallbackResponse:
    result = service.execute(
        HandleHyundaiOAuthCallbackCommand(
            code=code,
            state=state,
        )
    )

    return HyundaiOAuthCallbackResponse(
        status=result.status,
        session_id=result.session_id,
    )


@router.get("/session/{session_id}/status", response_model=SessionStatusResponse)
def get_login_session_status(
    session_id: str,
    service: GetLoginSessionStatusService = Depends(get_login_session_status_service),
) -> SessionStatusResponse:
    result = service.execute(GetLoginSessionStatusCommand(session_id=session_id))
    return SessionStatusResponse(
        status=result.status,
        user_id=result.user_id,
        name=result.name,
        cars=result.cars,
        temp_access_token=result.temp_access_token,
    )


@router.post("/confirm-car", response_model=ConfirmVehicleResponse)
def confirm_vehicle(
    request: ConfirmVehicleRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    service: ConfirmVehicleService = Depends(get_confirm_vehicle_service),
) -> ConfirmVehicleResponse:
    result = service.execute(
        ConfirmVehicleCommand(
            temp_access_token=extract_bearer_token(authorization),
            car_id=request.car_id,
            vin_hash=request.vin_hash,
        )
    )

    return ConfirmVehicleResponse(
        app_access_token=result.app_access_token,
        app_refresh_token=result.app_refresh_token,
        user_id=result.user_id,
        name=result.name,
        car_id=result.car_id,
        car=result.car,
    )


@router.post("/refresh", response_model=RefreshAccessTokenResponse)
def refresh_access_token(
    request: RefreshAccessTokenRequest,
    service: RefreshAccessTokenService = Depends(get_refresh_access_token_service),
) -> RefreshAccessTokenResponse:
    result = service.execute(
        RefreshAccessTokenCommand(refresh_token=request.refresh_token)
    )

    return RefreshAccessTokenResponse(
        app_access_token=result.app_access_token,
        app_refresh_token=result.app_refresh_token,
    )
