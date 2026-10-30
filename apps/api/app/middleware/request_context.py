import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.middleware.error_handler import internal_error_response
from app.utils.log import request_id_var

log = logging.getLogger("app.request")
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_QUIET_PATHS = {"/api/health"}


class RequestContextMiddleware:
    """Request ID, structured access log, and the last-resort 500.

    Sits inside CORS so even a 500 carries CORS headers and the browser shows the real error.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = False
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        began = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("unhandled exception")
            if started:
                raise
            status = 500
            await internal_error_response()(scope, receive, send_wrapper)
        finally:
            if scope["path"] not in _QUIET_PATHS:
                log.info(
                    "request",
                    extra={
                        "fields": {
                            "method": scope["method"],
                            "path": scope["path"],
                            "status": status,
                            "duration_ms": round((time.perf_counter() - began) * 1000, 1),
                        }
                    },
                )
            request_id_var.reset(token)
