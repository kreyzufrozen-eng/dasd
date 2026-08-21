"""Domain exceptions + centralized error handling.

Route handlers raise these instead of building `HTTPException(...)` ad hoc
in each endpoint — keeps the "not found" / "invalid input" / "conflict"
pattern in one place (DRY) and guarantees every error response, including
truly unexpected ones, has the same JSON shape:

    {"error": {"code": "not_found", "message": "..."}}

and that unhandled exceptions never leak a stack trace to the client —
they're logged server-side and returned as a generic 500.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base for all domain errors. status_code/code are class-level so
    subclasses only need to set a message."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class InvalidInputError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "invalid_input"


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default body for this is fine structurally but doesn't
        # match our {"error": {...}} envelope — normalize it.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("invalid_input", str(exc.errors())),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals (stack traces, DB errors, etc.) to the
        # client — log full detail server-side, return a generic message.
        logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "Internal server error"),
        )
