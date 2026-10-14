"""CSRF defence: unsafe methods on `/api/*` must carry `Origin` equal to `PUBLIC_APP_URL` (agents.md §4).

Pure ASGI, like the request-context middleware. The SPA uses fetch with cookies, and browsers always send
`Origin` on cross-site and same-site POSTs; a request without one is not from our SPA and is refused.
Machine callers that cannot send an Origin (the Paddle webhook) are listed in `EXEMPT_PATHS`, by exact
path, and must authenticate by signature instead.
"""

import structlog
from rm_contracts.problems import ProblemCode
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from rm_api.problems import problem_response

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
EXEMPT_PATHS = frozenset({"/api/webhooks/paddle"})  # exactly the signed webhook, nothing under a prefix
log = structlog.get_logger(__name__)


class OriginCheckMiddleware:
    def __init__(self, app: ASGIApp, *, allowed_origin: str) -> None:
        self.app = app
        self.allowed = allowed_origin.rstrip("/").lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if not path.startswith("/api/") or path in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        origin = Headers(scope=scope).get("origin", "").rstrip("/").lower()
        if origin != self.allowed:
            log.warning("origin_refused", path=path, had_origin=bool(origin))
            response = problem_response(
                Request(scope),
                status=403,
                code=ProblemCode.ORIGIN_NOT_ALLOWED,
                title="Origin not allowed",
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
