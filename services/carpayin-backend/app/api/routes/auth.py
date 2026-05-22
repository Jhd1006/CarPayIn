from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.api.deps import (
    get_create_qr_session_service,
    get_handle_hyundai_oauth_callback_service,
    get_login_session_status_service,
    get_start_hyundai_oauth_service,
)
from app.api.schemas.auth import (
    HyundaiOAuthCallbackResponse,
    QrSessionCreateRequest,
    QrSessionCreateResponse,
    SessionStatusResponse,
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
from app.application.auth.start_hyundai_oauth import (
    StartHyundaiOAuthCommand,
    StartHyundaiOAuthService,
)


router = APIRouter(prefix="/auth", tags=["Auth"])


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
