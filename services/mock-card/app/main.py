from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.card import router as card_router


app = FastAPI(title="Mock Card")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"code": "BAD_REQUEST", "message": str(exc)},
    )


app.include_router(card_router)
