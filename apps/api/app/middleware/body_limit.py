from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.middleware.error_handler import error_response


class _TooLarge(HTTPException):
    # An HTTPException on purpose: FastAPI converts any other exception raised while reading the
    # body into a generic 400, but lets HTTPException through to the 413 handler.
    def __init__(self) -> None:
        super().__init__(status_code=413)


class BodyLimitMiddleware:
    """Reject oversized bodies before they are buffered. Checks Content-Length up front and
    counts streamed bytes for chunked uploads that never declare a length."""

    def __init__(self, app: ASGIApp, *, default_limit: int, overrides: dict[str, int]) -> None:
        self.app = app
        self.default_limit = default_limit
        self.overrides = overrides

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.overrides.get(scope["path"], self.default_limit)
        headers = dict(scope["headers"])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._reject(scope, receive, send)
            return

        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if started:
                raise
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(413, "payload_too_large", "The request body is too large.")
        await response(scope, receive, send)
