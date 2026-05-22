from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.parking import router as parking_router


app = FastAPI(title="Car Pay-in Backend")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    error_code = str(exc)
    if error_code in {"session_not_found", "session_expired"}:
        status_code = 404
    elif error_code in {
        "invalid_token",
        "pms_auth_failed",
        "refresh_token_not_found",
        "refresh_token_revoked",
        "refresh_token_expired",
        "temp_token_expired",
    }:
        status_code = 401
    elif error_code in {"car_id_token_mismatch"}:
        status_code = 403
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
            }[status_code],
            "message": error_code,
        },
    )


app.include_router(auth_router)
app.include_router(parking_router)
