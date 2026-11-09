import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = "Not found."
_CODES = {404: "not_found", 405: "method_not_allowed"}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def _response(
    status: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(body.model_dump(), status_code=status, headers=headers)


class AppError(Exception):
    """Expected API error; rendered as the standard JSON shape with a fixed message."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.headers = dict(headers) if headers else None


def not_authenticated() -> AppError:
    return AppError(401, "not_authenticated", "Not signed in.")


def invalid_credentials() -> AppError:
    return AppError(401, "invalid_credentials", "Invalid email or password.")


def csrf_failed() -> AppError:
    return AppError(403, "csrf_failed", "Request blocked. Refresh the page and try again.")


def registration_not_allowed() -> AppError:
    return AppError(
        403,
        "registration_not_allowed",
        "We couldn't create an account with the details provided.",
    )


def email_taken() -> AppError:
    return AppError(409, "email_taken", "An account with this email already exists.")


def password_breached() -> AppError:
    return AppError(
        422,
        "password_breached",
        "This password has appeared in a data breach. Choose a different one.",
    )


def rate_limited(retry_after: int) -> AppError:
    return AppError(
        429,
        "rate_limited",
        "Too many attempts. Try again later.",
        headers={"Retry-After": str(max(1, retry_after))},
    )


def not_found() -> AppError:
    return AppError(404, "not_found", NOT_FOUND_MESSAGE)


def file_too_large() -> AppError:
    return AppError(413, "file_too_large", "This file is larger than 20 MB.")


def unsupported_file_type() -> AppError:
    return AppError(415, "unsupported_file_type", "Only PDF files can be uploaded.")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return _response(exc.status, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else code
        if exc.status_code == 404 and message == "Not Found":  # Starlette's routing default
            message = NOT_FOUND_MESSAGE
        return _response(exc.status_code, code, message, headers=dict(exc.headers or {}))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return _response(422, "validation_error", "Request validation failed", details)


class ServerErrorJSONMiddleware:
    """Pure ASGI: turns an unhandled exception into the standard JSON 500.

    Sits inside CORSMiddleware so the 500 carries CORS headers. Re-raises if the
    response has already started.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            if started:
                raise
            request = StarletteRequest(scope)
            logger.error(
                "Unhandled exception on %s %s",
                request.method,
                request.url.path,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            response = _response(500, "internal_error", "Internal server error")
            await response(scope, receive, send)
