import secrets

from api import SEPARATE_PATH, TOKEN_HEADER
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY = 2 * 1024 * 1024
LOOPBACK_HOST = "127.0.0.1"
BODY_TOO_LARGE = "request body too large"

Rejection = tuple[int, str]


class BodyTooLarge(HTTPException):
    """An HTTPException so FastAPI's body parsing re-raises it as 413, not 400."""

    def __init__(self) -> None:
        super().__init__(413, BODY_TOO_LARGE)


class RequestGuard:
    """Rejects bad Host, token or body size before the app reads the body."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        token: str,
        max_body: int = MAX_BODY,
        allowed_host: str = LOOPBACK_HOST,
    ) -> None:
        self.app = app
        self.token = token.encode()
        self.max_body = max_body
        self.allowed_host = allowed_host

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # OPTIONS is left to CORS (preflight) or the router (405); it never carries a body.
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        rejection = self._check_headers(scope)
        if rejection is not None:
            status, detail = rejection
            response = JSONResponse({"detail": detail}, status_code=status)
            await response(scope, receive, send)
            return
        await self.app(scope, self._capped(receive), send)

    def _check_headers(self, scope: Scope) -> Rejection | None:
        headers = Headers(scope=scope)
        if headers.get("host", "").split(":", 1)[0] != self.allowed_host:
            return 400, "invalid host"
        token = headers.get(TOKEN_HEADER, "").encode("latin-1")
        if not secrets.compare_digest(token, self.token):
            return 403, "invalid or missing token"
        if scope["method"] == "POST" and scope["path"] == SEPARATE_PATH:
            return self._check_content_length(headers.get("content-length"))
        return None

    def _check_content_length(self, value: str | None) -> Rejection | None:
        if value is None:
            return 411, "Content-Length required"
        if not (value.isascii() and value.isdigit()):
            return 400, "invalid Content-Length"
        if int(value) > self.max_body:
            return 413, BODY_TOO_LARGE
        return None

    def _capped(self, receive: Receive) -> Receive:
        # Catches bodies longer than their declared Content-Length.
        received = 0

        async def capped_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body:
                    raise BodyTooLarge()
            return message

        return capped_receive
