"""Expected application errors and their JSON representation.

Error responses have the shape ``{"error": {"code": str, "message": str}}``. Messages are written for
end users and never contain filesystem paths, stack traces or environment values.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("tenderflow")


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def not_found(what: str) -> AppError:
    return AppError("not_found", f"{what} was not found.", 404)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for err in exc.errors()[:5]:
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
            details.append(f"{loc}: {err.get('msg', 'invalid value')}" if loc else err.get("msg", "invalid"))
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_request", "message": "; ".join(details) or "Invalid request."}},
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:  # pragma: no cover - safety net
        # Log the exception type only: messages from parsers can contain document text.
        logger.error("Unexpected error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Something went wrong on the server."}},
        )
