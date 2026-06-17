import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.routes.dev import router as dev_router
from app.api.routes.pg import router as pg_router


app = FastAPI(title="Mock PG")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"code": "BAD_REQUEST", "message": str(exc)},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"code": "CONFLICT", "message": "duplicate_key"},
    )

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "commit": os.getenv("GIT_COMMIT", "unknown")}

app.include_router(dev_router)
app.include_router(pg_router)
