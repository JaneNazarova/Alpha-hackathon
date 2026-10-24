import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("alpha_backend")


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_trace(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled server error trace_id=%s path=%s", trace_id, request.url.path)
            response = JSONResponse(status_code=500, content={"error": {
                "code": "internal_error", "message": "Внутренняя ошибка сервера",
                "trace_id": trace_id}})
        response.headers["X-Trace-Id"] = trace_id
        return response
