"""Describe the error side of the API in OpenAPI (RM-264, L-027).

FastAPI documents only success responses and its own `HTTPValidationError`, but this API answers every
error as `application/problem+json` (`rm_api.problems`). This module rewrites the generated document so a
client generated from it sees the truth: a `Problem` schema, and for every operation the statuses it can
return, each with the problem `code`s that can come with it (`x-problem-codes`).

Derived from the routes: `401` behind a session, `403 ORIGIN_NOT_ALLOWED` for unsafe methods, `422` for
routes that take input, `400` for routes with a body, and the ever-present `500` and `503 NOT_READY`.
Written by hand is `EXTRA` below: the
statuses and codes a handler raises. `tests/unit/test_openapi_problems.py` checks that table against the
handlers' source (every code raised in a router is listed) and the smoke test checks it against real answers
(every status and code seen is listed).
"""

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from rm_contracts.problems import Problem, ProblemCode

from rm_api.deps import current_principal

C = ProblemCode
PROBLEM_MEDIA = "application/problem+json"
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
Errors = dict[int, tuple[ProblemCode, ...]]

# Hand-written: what each handler raises beyond the derived statuses. Key: "METHOD /path/template".
EXTRA: dict[str, Errors] = {
    "POST /api/auth/google": {
        401: (C.INVALID_GOOGLE_TOKEN, C.GOOGLE_EMAIL_UNVERIFIED, C.EMAIL_CONFIRMATION_REQUIRED),
    },
    "POST /api/auth/email/start": {429: (C.RATE_LIMITED,)},
    "POST /api/auth/email/verify": {401: (C.MAGIC_LINK_INVALID,)},
    "POST /api/auth/register": {422: (C.WEAK_PASSWORD,), 429: (C.RATE_LIMITED,)},
    "POST /api/auth/register/resend": {429: (C.RATE_LIMITED,)},
    "POST /api/auth/register/verify": {
        401: (C.AUTH_TOKEN_INVALID,),
        409: (C.ACCOUNT_EXISTS,),
        429: (C.RATE_LIMITED,),
    },
    "POST /api/auth/login": {401: (C.INVALID_CREDENTIALS,), 429: (C.RATE_LIMITED,)},
    "POST /api/auth/password/forgot": {429: (C.RATE_LIMITED,)},
    "POST /api/auth/password/reset": {
        401: (C.AUTH_TOKEN_INVALID,),
        422: (C.WEAK_PASSWORD,),
        429: (C.RATE_LIMITED,),
    },
    "POST /api/auth/password/change": {
        401: (C.INVALID_CREDENTIALS,),
        422: (C.WEAK_PASSWORD,),
        429: (C.RATE_LIMITED,),
    },
    "GET /api/me/export": {429: (C.RATE_LIMITED,)},
    "DELETE /api/me": {422: (C.CONFIRMATION_MISMATCH,)},
    "PUT /api/saved/{otodom_id}": {404: (C.NOT_FOUND,), 409: (C.SAVED_LIMIT_REACHED,)},
    "GET /api/interior/projects": {403: (C.FEATURE_NOT_IN_PLAN,)},
    "POST /api/interior/projects": {403: (C.FEATURE_NOT_IN_PLAN,), 409: (C.INTERIOR_LIMIT_REACHED,)},
    "GET /api/interior/projects/{project_id}": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "PUT /api/interior/projects/{project_id}": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "DELETE /api/interior/projects/{project_id}": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "POST /api/interior/projects/{project_id}/items": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        409: (C.INTERIOR_LIMIT_REACHED,),
    },
    "PUT /api/interior/projects/{project_id}/items/{item_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "DELETE /api/interior/projects/{project_id}/items/{item_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "POST /api/interior/projects/{project_id}/source": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        409: (C.INTERIOR_LIMIT_REACHED,),
        422: (C.IMAGE_REJECTED,),
        503: (C.MEDIA_STORAGE_UNAVAILABLE,),
    },
    "PUT /api/interior/projects/{project_id}/items/{item_id}/photo": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        422: (C.IMAGE_REJECTED,),
        503: (C.MEDIA_STORAGE_UNAVAILABLE,),
    },
    "GET /api/interior/projects/{project_id}/media/{media_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        503: (C.MEDIA_STORAGE_UNAVAILABLE,),
    },
    "GET /api/interior/catalogue": {403: (C.FEATURE_NOT_IN_PLAN,)},
    "GET /api/interior/projects/{project_id}/catalogue/search": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        503: (C.CATALOGUE_UNAVAILABLE,),
    },
    "POST /api/interior/projects/{project_id}/selections": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        409: (C.INTERIOR_LIMIT_REACHED, C.OFFER_UNAVAILABLE),
        503: (C.CATALOGUE_UNAVAILABLE,),
    },
    "PUT /api/interior/projects/{project_id}/selections/{selection_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "DELETE /api/interior/projects/{project_id}/selections/{selection_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "POST /api/interior/projects/{project_id}/selections/{selection_id}/refresh": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        409: (C.OFFER_UNAVAILABLE,),
        503: (C.CATALOGUE_UNAVAILABLE,),
    },
    "GET /api/interior/catalogue/demo-image/{product_id}/{variant_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "POST /api/interior/projects/{project_id}/generations": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        409: (C.GENERATION_CONFLICT,),
        503: (C.GENERATION_UNAVAILABLE,),
    },
    "GET /api/interior/projects/{project_id}/generations": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "GET /api/interior/projects/{project_id}/generations/{generation_id}": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "POST /api/interior/projects/{project_id}/generations/{generation_id}/cancel": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
        409: (C.GENERATION_CONFLICT,),
    },
    "POST /api/interior/projects/{project_id}/revisions": {
        403: (C.FEATURE_NOT_IN_PLAN,),
        404: (C.NOT_FOUND,),
    },
    "POST /api/audits": {
        402: (C.QUOTA_EXHAUSTED,),
        403: (C.BILLING_HOLD, C.FEATURE_NOT_IN_PLAN),
        409: (C.AUDIT_IN_PROGRESS, C.IDEMPOTENCY_CONFLICT),
        422: (C.INVALID_LISTING_REF,),
    },
    "GET /api/audits/{audit_id}": {404: (C.NOT_FOUND,)},
    "GET /api/audits/{audit_id}/events": {404: (C.NOT_FOUND,)},
    "GET /api/audits/{audit_id}/media": {404: (C.NOT_FOUND,)},
    "GET /api/market/locations/{location_id}": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "GET /api/market/locations/{location_id}/history": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "GET /api/market/locations/{location_id}/context": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "GET /api/market/locations/{location_id}/ranking": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "GET /api/market/locations/{location_id}/districts": {403: (C.FEATURE_NOT_IN_PLAN,), 404: (C.NOT_FOUND,)},
    "POST /api/billing/checkout": {
        403: (C.EMAIL_NOT_VERIFIED, C.BILLING_HOLD),
        409: (C.IDEMPOTENCY_CONFLICT,),
        429: (C.RATE_LIMITED,),
        502: (C.BILLING_PROVIDER_ERROR,),
        503: (C.BILLING_UNAVAILABLE,),
    },
    "GET /api/billing/purchases/{purchase_id}": {404: (C.NOT_FOUND,)},
    "GET /api/billing/purchases/{purchase_id}/invoice": {
        404: (C.NOT_FOUND,),
        409: (C.PURCHASE_NOT_REFUNDABLE,),
        429: (C.RATE_LIMITED,),
        502: (C.BILLING_PROVIDER_ERROR,),
        503: (C.BILLING_UNAVAILABLE,),
    },
    "PUT /api/admin/flags/{key}": {404: (C.NOT_FOUND,)},
    "PUT /api/admin/flags/{key}/overrides/{user_id}": {404: (C.NOT_FOUND,)},
    "POST /api/admin/credits/adjust": {
        404: (C.NOT_FOUND,),
        409: (C.CREDIT_BELOW_ZERO,),
        422: (C.VALIDATION_ERROR,),
    },
    "POST /api/admin/users/{user_id}/billing-hold/clear": {404: (C.NOT_FOUND,)},
    "POST /api/admin/billing/purchases/{purchase_id}/refund": {
        409: (C.PURCHASE_NOT_REFUNDABLE, C.REFUND_NEEDS_REVIEW),
        502: (C.BILLING_PROVIDER_ERROR,),
        503: (C.BILLING_UNAVAILABLE,),
    },
}
ADMIN_PREFIX = "/api/admin/"


def _needs_session(route: APIRoute) -> bool:
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is current_principal:
            return True
        stack.extend(dep.dependencies)
    return False


def derived_errors(route: APIRoute, method: str, takes_input: bool, has_body: bool = False) -> Errors:
    errors: dict[int, set[ProblemCode]] = {500: {C.INTERNAL}, 503: {C.NOT_READY}}
    if method in UNSAFE:
        errors.setdefault(403, set()).add(C.ORIGIN_NOT_ALLOWED)
    if _needs_session(route):
        errors.setdefault(401, set()).add(C.UNAUTHENTICATED)
    if route.path.startswith(ADMIN_PREFIX):
        errors.setdefault(403, set()).add(C.ADMIN_ONLY)
    if takes_input:
        errors.setdefault(422, set()).add(C.VALIDATION_ERROR)
    if has_body:  # a body that is not decodable JSON is refused before validation, as a plain HTTP 400
        errors.setdefault(400, set()).add(C.HTTP_ERROR)
    for status, codes in EXTRA.get(f"{method} {route.path}", {}).items():
        errors.setdefault(status, set()).update(codes)
    return {status: tuple(sorted(codes)) for status, codes in sorted(errors.items())}


def _response(status: int, codes: tuple[ProblemCode, ...]) -> dict[str, Any]:
    return {
        "description": f"Problem: {', '.join(codes)}",
        "content": {PROBLEM_MEDIA: {"schema": {"$ref": "#/components/schemas/Problem"}}},
        "x-problem-codes": [str(c) for c in codes],
    }


def document_problems(routers: Sequence[APIRouter], schema: dict[str, Any]) -> dict[str, Any]:
    components: dict[str, Any] = schema["components"]["schemas"]
    for name in ("HTTPValidationError", "ValidationError"):
        components.pop(name, None)
    problem = Problem.model_json_schema(ref_template="#/components/schemas/{model}")
    components.update(problem.pop("$defs", {}))
    components["Problem"] = problem
    routes = {
        (method, route.path): route
        for router in routers
        for route in router.routes
        if isinstance(route, APIRoute) and route.include_in_schema
        for method in route.methods or ()
    }
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            route = routes[(method.upper(), path)]
            responses: dict[str, Any] = operation["responses"]
            request_body: dict[str, Any] = operation.get("requestBody") or {}
            body_types: dict[str, Any] = request_body.get("content", {})
            has_body = "application/json" in body_types  # a raw upload has no JSON to be undecodable
            takes_input = bool(operation.get("parameters") or body_types)
            responses.pop("422", None)
            for status, codes in derived_errors(route, method.upper(), takes_input, has_body).items():
                responses[str(status)] = _response(status, codes)
    return schema


def install_problem_docs(app: FastAPI, routers: Sequence[APIRouter]) -> None:
    """Replace `app.openapi` with a version that documents errors as problem+json (cached like FastAPI's)."""
    base = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None or "Problem" not in app.openapi_schema["components"]["schemas"]:
            document_problems(routers, base())
        return app.openapi_schema or {}

    setattr(app, "openapi", openapi)  # noqa: B010  (FastAPI documents this override; type checkers disagree)
