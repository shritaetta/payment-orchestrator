from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import uuid
from app.api import endpoints
from app.logging import setup_logging, set_correlation_id
import typing
from fastapi import Response

setup_logging()

app = FastAPI(title="Payment Orchestrator")

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: typing.Callable[[Request], typing.Awaitable[Response]]) -> Response:
        corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        set_correlation_id(corr_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response

app.add_middleware(CorrelationIdMiddleware)

app.include_router(endpoints.router, prefix="/payments", tags=["payments"])

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
