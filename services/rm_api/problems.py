"""RFC 9457 `application/problem+json` responses with stable codes from `rm_contracts.problems`.

Foreign tenant resources are answered with `Problem.not_found()`: 404, never 403 (agents.md §4).
"""

import re
from collections.abc import Sequence
from typing import Any, cast

import sentry_sdk
import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from rm_contracts.problems import ProblemCode
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"
MAX_VALIDATION_ERRORS = 20
log = structlog.get_logger(__name__)


class Problem(Exception):
    """Raise from route code or dependencies; the handler renders the response."""

    def __init__(
        self,
        status: int,
        code: ProblemCode,
        title: str,
        detail: str | None = None,
        *,
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(f"{code}: {title}")
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.headers = headers
        self.extra = extra

    @classmethod
    def not_found(cls, what: str = "Resource") -> "Problem":
        return cls(404, ProblemCode.NOT_FOUND, f"{what} not found")

    @classmethod
    def unauthorized(cls, code: ProblemCode, title: str) -> "Problem":
        return cls(401, code, title)

    @classmethod
    def rate_limited(cls, retry_after_s: int) -> "Problem":
        return cls(
            429,
            ProblemCode.RATE_LIMITED,
            "Too many requests",
            headers={"Retry-After": str(retry_after_s)},
        )


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else None


def problem_response(
    request: Request,
    *,
    status: int,
    code: ProblemCode,
    title: str,
    detail: str | None = None,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:rentmonitor:problem:{code.value}",
        "title": title,
        "status": status,
        "code": code.value,
        "instance": request.url.path,
        **extra,
    }
    if detail:
        body["detail"] = detail
    out_headers = dict(headers or {})
    if (rid := _request_id(request)) is not None:
        body["request_id"] = rid
        out_headers["x-request-id"] = rid  # the 500 path bypasses RequestContextMiddleware's send wrapper
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=out_headers)


async def _problem(request: Request, exc: Exception) -> JSONResponse:
    exc = cast("Problem", exc)
    return problem_response(
        request,
        status=exc.status,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        headers=exc.headers,
        **exc.extra,
    )


async def _validation(request: Request, exc: Exception) -> JSONResponse:
    exc = cast("RequestValidationError", exc)
    # Never echo the offending input back: it can hold secrets or personal data.
    errors = [
        {"loc": [str(p) for p in e["loc"]], "type": e["type"], "msg": e["msg"]}
        for e in exc.errors()[:MAX_VALIDATION_ERRORS]
    ]
    return problem_response(
        request,
        status=422,
        code=ProblemCode.VALIDATION_ERROR,
        title="Request validation failed",
        errors=errors,
    )


def build_route_table(routers: Sequence[APIRouter]) -> list[tuple[re.Pattern[str], frozenset[str]]]:
    """`(path pattern, methods)` for every route of the included routers.

    FastAPI keeps included routers behind opaque objects, so the table is made from the routers themselves
    (called once from `create_app`)."""
    return [
        (route.path_regex, frozenset(route.methods or ()))
        for router in routers
        for route in router.routes
        if isinstance(route, APIRoute)
    ]


def allowed_methods(request: Request) -> list[str]:
    """Every method any route offers for this path.

    Starlette's own `Allow` lists only the first matching route, which is wrong where one path has a route per
    method (`GET /api/audits`, `POST /api/audits`)."""
    path = request.url.path
    methods: set[str] = set()
    for pattern, offered in getattr(request.app.state, "route_table", ()):
        if pattern.match(path):
            methods.update(offered)
    for route in request.app.routes:  # routes added straight to the app
        pattern = getattr(route, "path_regex", None)
        if pattern is not None and pattern.match(path):
            methods.update(getattr(route, "methods", None) or ())
    return sorted(methods)


async def _http(request: Request, exc: Exception) -> JSONResponse:
    exc = cast("StarletteHTTPException", exc)
    code = ProblemCode.NOT_FOUND if exc.status_code == 404 else ProblemCode.HTTP_ERROR
    title = "Resource not found" if exc.status_code == 404 else "HTTP error"
    headers = dict(exc.headers or {})
    if exc.status_code == 405 and (methods := allowed_methods(request)):  # RFC 9110 section 15.5.6
        headers["Allow"] = ", ".join(methods)
    return problem_response(request, status=exc.status_code, code=code, title=title, headers=headers)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", exc_info=exc, path=request.url.path)
    sentry_sdk.capture_exception(exc)
    return problem_response(request, status=500, code=ProblemCode.INTERNAL, title="Internal error")


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Problem, _problem)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(Exception, _unhandled)
