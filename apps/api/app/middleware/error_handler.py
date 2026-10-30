import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")

_STATUS_CODES = {
    400: ("bad_request", "The request could not be processed."),
    401: ("not_authenticated", "Authentication required."),
    403: ("forbidden", "You do not have permission to do this."),
    404: ("not_found", "Resource not found."),
    405: ("method_not_allowed", "Method not allowed."),
    413: ("payload_too_large", "The request body is too large."),
    415: ("unsupported_media_type", "Unsupported media type."),
    429: ("rate_limited", "Too many requests. Try again later."),
}


class AppError(Exception):
    """Raise anywhere to return { error: { code, message, details? } } with this status."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse({"error": body}, status_code=status_code, headers=headers)


def internal_error_response() -> JSONResponse:
    return error_response(500, "internal_error", "Something went wrong on our side.")


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(AppError, exc)
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    code, message = _STATUS_CODES.get(
        exc.status_code, (f"http_{exc.status_code}", "Request failed.")
    )
    return error_response(exc.status_code, code, message, headers=dict(exc.headers or {}))


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    # Field, message and type only. Never echo the submitted input back.
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    return error_response(422, "validation_error", "The request is invalid.", details)


async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled exception", exc_info=exc)
    return internal_error_response()


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
