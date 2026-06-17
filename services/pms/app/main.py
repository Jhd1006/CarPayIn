import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes.dev import router as dev_router
from app.api.routes.pms import router as pms_router


app = FastAPI(title="Mock PMS")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    error_code = str(exc)
    status_code = 404 if error_code == "session_not_found" else 400
    return JSONResponse(
        status_code=status_code,
        content={
            "code": "NOT_FOUND" if status_code == 404 else "BAD_REQUEST",
            "message": error_code,
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


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # 동시 LPR 진입 등 유니크 제약 위반 — 이미 활성 세션이 있다는 의미
    return JSONResponse(
        status_code=409,
        content={"code": "CONFLICT", "message": "duplicate_active_session"},
    )

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "commit": os.getenv("GIT_COMMIT", "unknown")}
    
app.include_router(dev_router)
app.include_router(pms_router)
