import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from app.api.routes.auth import router as auth_router
from app.api.routes.card import router as card_router
from app.api.routes.dev import router as dev_router
from app.api.routes.parking import router as parking_router
from app.api.routes.payment import router as payment_router
from app.api.routes.load_test import router as load_test_router
from app.infra.redis import redis_client
from app.infra.workers.notify_retry_worker import NotifyRetryWorker

bearer_scheme = HTTPBearer(auto_error=False)


def _build_retry_worker() -> NotifyRetryWorker:
    from app.api.deps import notification_publisher, pms_client
    return NotifyRetryWorker(
        redis_client=redis_client,
        notification_publisher=notification_publisher,
        pms_client=pms_client,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = _build_retry_worker()
    worker.start()
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(
    title="Car Pay-in Backend",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
    dependencies=[Depends(bearer_scheme)],
)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "commit": os.getenv("GIT_COMMIT", "unknown")}


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    error_code = str(exc)
    if error_code == "session_not_found" and request.url.path != "/payment":
        status_code = 404
    elif error_code in {"session_expired", "session_not_active"}:
        status_code = 404
    elif error_code in {
        "invalid_token",
        "invalid_signature",
        "pms_auth_failed",
        "refresh_token_not_found",
        "refresh_token_revoked",
        "refresh_token_expired",
        "temp_token_expired",
    }:
        status_code = 401
    elif error_code == "session_car_id_mismatch":
        status_code = 403
    elif error_code in {"quote_not_found", "amount_currency_mismatch"}:
        status_code = 409
    elif error_code in {"molit_verification_failed"}:
        status_code = 422
    else:
        status_code = 400

    return JSONResponse(
        status_code=status_code,
        content={
            "code": {
                400: "BAD_REQUEST",
                401: "UNAUTHORIZED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                409: "CONFLICT",
                422: "UNPROCESSABLE_ENTITY",
            }[status_code],
            "message": error_code,
        },
    )


@app.exception_handler(LookupError)
async def lookup_error_handler(request: Request, exc: LookupError):
    return JSONResponse(
        status_code=404,
        content={
            "code": "NOT_FOUND",
            "message": str(exc),
        },
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(
        status_code=401,
        content={
            "code": "UNAUTHORIZED",
            "message": str(exc),
        },
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=502,
        content={
            "code": "BAD_GATEWAY",
            "message": str(exc),
        },
    )


app.include_router(auth_router)
app.include_router(card_router)
app.include_router(dev_router)
app.include_router(parking_router)
app.include_router(payment_router)
app.include_router(load_test_router)