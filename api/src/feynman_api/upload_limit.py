from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from feynman_api.errors import ErrorBody, ErrorResponse, file_too_large


def _too_large_response() -> JSONResponse:
    err = file_too_large()
    body = ErrorResponse(error=ErrorBody(code=err.code, message=err.message))
    return JSONResponse(body.model_dump(), status_code=err.status)


class BodySizeLimitMiddleware:
    """Pure ASGI cap on the request body of `POST <path>`.

    A declared Content-Length over the cap gets a 413 without reading the body. Otherwise
    the body bytes are counted; once over the cap, `receive` reports a disconnect (so the
    multipart parser stops), the inner app's response is dropped, and the 413 is sent here.
    """

    def __init__(self, app: ASGIApp, *, path: str, max_bytes: int) -> None:
        self.app = app
        self.path = path
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await _too_large_response()(scope, receive, send)
            return

        count = 0
        exceeded = False
        started = False

        async def counting_receive() -> Message:
            nonlocal count, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                count += len(message.get("body", b""))
                if count > self.max_bytes:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if exceeded:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            # The parser may fail once receive reports a disconnect; that is our 413.
            if not exceeded:
                raise
        if exceeded and not started:
            await _too_large_response()(scope, receive, send)
