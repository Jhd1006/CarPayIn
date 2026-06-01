from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.pg import router as pg_router


app = FastAPI(title="Mock PG")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"code": "BAD_REQUEST", "message": str(exc)},
    )

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}

app.include_router(pg_router)
