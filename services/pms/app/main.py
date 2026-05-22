from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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


app.include_router(pms_router)
