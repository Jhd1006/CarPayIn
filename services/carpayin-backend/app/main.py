from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.parking import router as parking_router
from app.api.routes.payment import router as payment_router


app = FastAPI(title="Car Pay-in Backend")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    error_code = str(exc)
    if error_code == "session_not_found" and request.url.path != "/payment":
        status_code = 404
    elif error_code in {"session_expired", "session_not_active"}:
        status_code = 404
    elif error_code in {"invalid_token", "pms_auth_failed"}:
        status_code = 401
    elif error_code in {"car_id_token_mismatch", "session_car_id_mismatch"}:
        status_code = 403
    elif error_code in {"quote_not_found", "amount_currency_mismatch"}:
        status_code = 409
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
            }[status_code],
            "message": error_code,
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
app.include_router(parking_router)
app.include_router(payment_router)
