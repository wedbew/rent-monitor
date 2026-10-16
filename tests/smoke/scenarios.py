"""The scenario registry: every API operation, driven like a browser would (#263, FRONTEND-PLAN.md §3).

One registry, two lanes. `tests/smoke/test_api_smoke.py` runs every scenario in-process and validates the
response against `docs/openapi.json`; `scripts/capture_api_samples.py` runs the same scenarios over loopback
HTTP and keeps the exchanges as local samples. A scenario is keyed by `"METHOD /path/template"` (the
OpenAPI operation), has a name, the status it must answer, and returns the exchange it is about.

Evidence class: fake provider data (see `world.py`). Hand-built listings, no real advert or person.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from listings import FRACTIONAL_AD, RENT_AD, SUCCESS
from rm_core.paddle import PaddleError
from rm_worker.clients.otodom import ListingGone, UpstreamBlocked
from world import LOGIN_PHRASE, Actor, Exchange, World

Run = Callable[[World], Awaitable[Exchange]]


@dataclass(frozen=True)
class Scenario:
    key: str  # "POST /api/audits"
    name: str
    status: int
    run: Run
    note: str = ""

    @property
    def id(self) -> str:
        return f"{self.key} :: {self.name}"


SCENARIOS: list[Scenario] = []


def scenario(key: str, name: str, status: int, note: str = "") -> Callable[[Run], Run]:
    def register(run: Run) -> Run:
        SCENARIOS.append(Scenario(key, name, status, run, note))
        return run

    return register


def gmail() -> str:
    return f"smoke-{uuid4().hex[:10]}@gmail.com"


def token40() -> str:
    return uuid4().hex + uuid4().hex[:8]  # 40 url-safe characters that match no stored token


# =============================================================================================== auth
@scenario("POST /api/auth/google", "new_account", 200)
async def google_new(w: World) -> Exchange:
    email = gmail()
    w._emails.append(email)
    return await w.send(
        w.anonymous(),
        "POST",
        "/api/auth/google",
        json={"credential": w.google_token(sub=f"sub-{uuid4().hex}", email=email, name="Anna Przykład")},
    )


@scenario("POST /api/auth/google", "returning_account", 200)
async def google_returning(w: World) -> Exchange:
    email, sub = gmail(), f"sub-{uuid4().hex}"
    w._emails.append(email)
    anon = w.anonymous()
    token = w.google_token(sub=sub, email=email)
    await w.send(anon, "POST", "/api/auth/google", json={"credential": token})
    return await w.send(anon, "POST", "/api/auth/google", json={"credential": token})


@scenario("POST /api/auth/google", "invalid_token", 401)
async def google_invalid(w: World) -> Exchange:
    return await w.send(
        w.anonymous(), "POST", "/api/auth/google", json={"credential": "not-a-google-token-" + "x" * 30}
    )


@scenario("POST /api/auth/google", "email_unverified", 401)
async def google_unverified(w: World) -> Exchange:
    token = w.google_token(sub=f"sub-{uuid4().hex}", email=gmail(), email_verified=False)
    return await w.send(w.anonymous(), "POST", "/api/auth/google", json={"credential": token})


@scenario("POST /api/auth/google", "email_confirmation_required", 401)
async def google_needs_confirmation(w: World) -> Exchange:
    token = w.google_token(sub=f"sub-{uuid4().hex}", email=f"smoke-{uuid4().hex[:8]}@example.test")
    return await w.send(w.anonymous(), "POST", "/api/auth/google", json={"credential": token})


@scenario("POST /api/auth/google", "validation_error", 422)
async def google_validation(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/google", json={"credential": "short"})


@scenario("POST /api/auth/email/start", "accepted", 204)
async def email_start(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/email/start", json={"email": w.new_email("magic")})


@scenario("POST /api/auth/email/start", "validation_error", 422)
async def email_start_invalid(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/email/start", json={"email": "not-an-email"})


@scenario("POST /api/auth/email/start", "rate_limited", 429)
async def email_start_limited(w: World) -> Exchange:
    anon, email = w.anonymous(), w.new_email("magic")
    last = await w.send(anon, "POST", "/api/auth/email/start", json={"email": email})
    for _ in range(5):
        last = await w.send(anon, "POST", "/api/auth/email/start", json={"email": email})
    return last


@scenario("POST /api/auth/email/verify", "signed_in", 200)
async def email_verify(w: World) -> Exchange:
    anon, email = w.anonymous(), w.new_email("magic")
    await w.send(anon, "POST", "/api/auth/email/start", json={"email": email})
    return await w.send(anon, "POST", "/api/auth/email/verify", json={"token": w.mail.magic_token(email)})


@scenario("POST /api/auth/email/verify", "link_invalid", 401)
async def email_verify_invalid(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/email/verify", json={"token": token40()})


@scenario("POST /api/auth/email/verify", "validation_error", 422)
async def email_verify_validation(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/email/verify", json={"token": "short"})


@scenario("POST /api/auth/register", "accepted", 202)
async def register(w: World) -> Exchange:
    return await w.send(
        w.anonymous(),
        "POST",
        "/api/auth/register",
        json={"email": w.new_email("reg"), "password": LOGIN_PHRASE},
    )


@scenario("POST /api/auth/register", "address_already_has_an_account", 202, "same answer as a new address")
async def register_existing(w: World) -> Exchange:
    existing = await w.user(label="taken")
    return await w.send(
        w.anonymous(), "POST", "/api/auth/register", json={"email": existing.email, "password": LOGIN_PHRASE}
    )


@scenario("POST /api/auth/register", "weak_password", 422)
async def register_weak(w: World) -> Exchange:
    return await w.send(
        w.anonymous(),
        "POST",
        "/api/auth/register",
        json={"email": w.new_email("reg"), "password": "password1234"},
    )


@scenario("POST /api/auth/register", "validation_error", 422)
async def register_invalid(w: World) -> Exchange:
    return await w.send(
        w.anonymous(), "POST", "/api/auth/register", json={"email": "nope", "password": "short"}
    )


@scenario("POST /api/auth/register/resend", "accepted", 202)
async def register_resend(w: World) -> Exchange:
    anon, email = w.anonymous(), w.new_email("reg")
    await w.send(anon, "POST", "/api/auth/register", json={"email": email, "password": LOGIN_PHRASE})
    return await w.send(anon, "POST", "/api/auth/register/resend", json={"email": email})


@scenario("POST /api/auth/register/resend", "no_pending_registration", 202, "same answer, nothing sent")
async def register_resend_none(w: World) -> Exchange:
    return await w.send(
        w.anonymous(), "POST", "/api/auth/register/resend", json={"email": w.new_email("reg")}
    )


@scenario("POST /api/auth/register/resend", "validation_error", 422)
async def register_resend_invalid(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/register/resend", json={"email": "nope"})


@scenario("POST /api/auth/register/verify", "account_created", 200)
async def register_verify(w: World) -> Exchange:
    anon, email = w.anonymous(), w.new_email("reg")
    await w.send(anon, "POST", "/api/auth/register", json={"email": email, "password": LOGIN_PHRASE})
    return await w.send(
        anon, "POST", "/api/auth/register/verify", json={"token": w.mail.token("register", email)}
    )


@scenario("POST /api/auth/register/verify", "link_invalid", 401)
async def register_verify_invalid(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/register/verify", json={"token": token40()})


@scenario("POST /api/auth/register/verify", "account_exists", 409)
async def register_verify_exists(w: World) -> Exchange:
    anon, email = w.anonymous(), w.new_email("reg")
    await w.send(anon, "POST", "/api/auth/register", json={"email": email, "password": LOGIN_PHRASE})
    await w.user(email=email)  # someone else made the account while the link was in the inbox
    return await w.send(
        anon, "POST", "/api/auth/register/verify", json={"token": w.mail.token("register", email)}
    )


@scenario("POST /api/auth/register/verify", "validation_error", 422)
async def register_verify_validation(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/register/verify", json={"token": "x"})


@scenario("POST /api/auth/login", "signed_in", 200)
async def login(w: World) -> Exchange:
    who = await w.user(label="login", password=LOGIN_PHRASE)
    return await w.send(
        w.anonymous(), "POST", "/api/auth/login", json={"email": who.email, "password": LOGIN_PHRASE}
    )


@scenario("POST /api/auth/login", "wrong_password", 401)
async def login_wrong(w: World) -> Exchange:
    who = await w.user(label="login", password=LOGIN_PHRASE)
    return await w.send(
        w.anonymous(), "POST", "/api/auth/login", json={"email": who.email, "password": "wrong-password-1"}
    )


@scenario("POST /api/auth/login", "unknown_address", 401, "same answer as a wrong password")
async def login_unknown(w: World) -> Exchange:
    return await w.send(
        w.anonymous(),
        "POST",
        "/api/auth/login",
        json={"email": w.new_email("ghost"), "password": LOGIN_PHRASE},
    )


@scenario("POST /api/auth/login", "rate_limited", 429)
async def login_limited(w: World) -> Exchange:
    anon, email = w.anonymous(), w.new_email("login")
    last = await w.send(anon, "POST", "/api/auth/login", json={"email": email, "password": LOGIN_PHRASE})
    for _ in range(10):
        last = await w.send(anon, "POST", "/api/auth/login", json={"email": email, "password": LOGIN_PHRASE})
    return last


@scenario("POST /api/auth/login", "validation_error", 422)
async def login_validation(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/login", json={"email": "x", "password": ""})


@scenario("POST /api/auth/password/forgot", "accepted", 202)
async def forgot(w: World) -> Exchange:
    who = await w.user(label="forgot")
    return await w.send(w.anonymous(), "POST", "/api/auth/password/forgot", json={"email": who.email})


@scenario("POST /api/auth/password/forgot", "unknown_address", 202, "same answer, nothing sent")
async def forgot_unknown(w: World) -> Exchange:
    return await w.send(
        w.anonymous(), "POST", "/api/auth/password/forgot", json={"email": w.new_email("ghost")}
    )


@scenario("POST /api/auth/password/forgot", "validation_error", 422)
async def forgot_validation(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/password/forgot", json={"email": "x"})


@scenario("POST /api/auth/password/reset", "password_set", 204)
async def reset(w: World) -> Exchange:
    who, anon = await w.user(label="reset"), w.anonymous()
    await w.send(anon, "POST", "/api/auth/password/forgot", json={"email": who.email})
    return await w.send(
        anon,
        "POST",
        "/api/auth/password/reset",
        json={"token": w.mail.token("reset", who.email), "password": "a-brand-new-passphrase-77"},
    )


@scenario("POST /api/auth/password/reset", "link_invalid", 401)
async def reset_invalid(w: World) -> Exchange:
    return await w.send(
        w.anonymous(),
        "POST",
        "/api/auth/password/reset",
        json={"token": token40(), "password": "a-brand-new-passphrase-77"},
    )


@scenario("POST /api/auth/password/reset", "weak_password", 422)
async def reset_weak(w: World) -> Exchange:
    who, anon = await w.user(label="reset"), w.anonymous()
    await w.send(anon, "POST", "/api/auth/password/forgot", json={"email": who.email})
    return await w.send(
        anon,
        "POST",
        "/api/auth/password/reset",
        json={"token": w.mail.token("reset", who.email), "password": "password1234"},
    )


@scenario("POST /api/auth/password/change", "changed", 204)
async def change(w: World) -> Exchange:
    who = await w.user(label="change", password=LOGIN_PHRASE)
    return await w.send(
        who,
        "POST",
        "/api/auth/password/change",
        json={"current_password": LOGIN_PHRASE, "new_password": "a-brand-new-passphrase-77"},
    )


@scenario("POST /api/auth/password/change", "wrong_current_password", 401)
async def change_wrong(w: World) -> Exchange:
    who = await w.user(label="change", password=LOGIN_PHRASE)
    return await w.send(
        who,
        "POST",
        "/api/auth/password/change",
        json={"current_password": "not-my-password-1", "new_password": "a-brand-new-passphrase-77"},
    )


@scenario("POST /api/auth/password/change", "weak_new_password", 422)
async def change_weak(w: World) -> Exchange:
    who = await w.user(label="change", password=LOGIN_PHRASE)
    return await w.send(
        who,
        "POST",
        "/api/auth/password/change",
        json={"current_password": LOGIN_PHRASE, "new_password": "password1234"},
    )


@scenario("GET /api/auth/sessions", "three_sessions", 200)
async def sessions(w: World) -> Exchange:
    return await w.send(await w.user(label="sessions", sessions=3), "GET", "/api/auth/sessions")


@scenario("GET /api/auth/sessions", "one_session", 200)
async def sessions_one(w: World) -> Exchange:
    return await w.send(await w.user(label="sessions"), "GET", "/api/auth/sessions")


@scenario("POST /api/auth/signout", "signed_out", 204)
async def signout(w: World) -> Exchange:
    return await w.send(await w.user(label="out"), "POST", "/api/auth/signout")


@scenario("POST /api/auth/signout", "not_signed_in", 204, "idempotent: still clears the cookie")
async def signout_anonymous(w: World) -> Exchange:
    return await w.send(w.anonymous(), "POST", "/api/auth/signout")


@scenario("POST /api/auth/signout-all", "signed_out_everywhere", 204)
async def signout_all(w: World) -> Exchange:
    return await w.send(await w.user(label="outall", sessions=3), "POST", "/api/auth/signout-all")


# ================================================================================================== me
@scenario("GET /api/me", "with_credits_and_flags", 200)
async def me(w: World) -> Exchange:
    await w.add_flag("smoke_on", description="on for everyone", enabled_default=True)
    return await w.send(await w.user(label="me", credits=7), "GET", "/api/me")


@scenario("GET /api/me", "no_credits_unverified", 200)
async def me_unverified(w: World) -> Exchange:
    return await w.send(await w.user(label="me", credits=0, verified=False), "GET", "/api/me")


@scenario("GET /api/me", "admin", 200)
async def me_admin(w: World) -> Exchange:
    return await w.send(await w.user(label="admin", role="admin"), "GET", "/api/me")


@scenario("GET /api/me", "upstream_breaker_open", 200, "Otodom circuit breaker tripped")
async def me_breaker(w: World) -> Exchange:
    from rm_core.throttle import OTODOM_HOST, trip_breaker  # noqa: PLC0415

    who = await w.user(label="me")
    async with w.sm() as s, s.begin():
        await trip_breaker(s, OTODOM_HOST, reason="captcha")
    try:
        return await w.send(who, "GET", "/api/me")
    finally:
        await w.sql("DELETE FROM app.host_throttle WHERE host = :h", h=OTODOM_HOST)


@scenario("GET /api/me/export", "export", 200)
async def export(w: World) -> Exchange:
    who = await w.user(label="export")
    refs = await w.seed_audits(who, 2)
    await w.send(who, "PUT", f"/api/saved/{refs[0]}", json={"note": "Do obejrzenia w sobotę"})
    return await w.send(who, "GET", "/api/me/export")


@scenario("GET /api/me/export", "rate_limited", 429)
async def export_limited(w: World) -> Exchange:
    who = await w.user(label="export")
    last = await w.send(who, "GET", "/api/me/export")
    for _ in range(5):
        last = await w.send(who, "GET", "/api/me/export")
    return last


@scenario("DELETE /api/me", "erased", 204)
async def delete_me(w: World) -> Exchange:
    who = await w.user(label="erase")
    return await w.send(who, "DELETE", "/api/me", json={"confirm_email": who.email})


@scenario("DELETE /api/me", "confirmation_mismatch", 422)
async def delete_me_mismatch(w: World) -> Exchange:
    who = await w.user(label="erase")
    return await w.send(who, "DELETE", "/api/me", json={"confirm_email": "someone-else@example.test"})


# =============================================================================================== saved
@scenario("GET /api/saved", "empty", 200)
async def saved_empty(w: World) -> Exchange:
    return await w.send(await w.user(label="saved"), "GET", "/api/saved")


@scenario("GET /api/saved", "five_with_notes", 200)
async def saved_many(w: World) -> Exchange:
    who = await w.user(label="saved")
    refs = await w.seed_audits(who, 5)
    notes = [None, "Sprawdzić czynsz", "Zbyt drogo", "Drugi pokój bez okna", "Wrócić po negocjacjach"]
    for ref, note in zip(refs, notes, strict=True):
        await w.send(who, "PUT", f"/api/saved/{ref}", json={"note": note})
    return await w.send(who, "GET", "/api/saved")


@scenario("GET /api/saved", "validation_error", 422)
async def saved_validation(w: World) -> Exchange:
    return await w.send(await w.user(label="saved"), "GET", "/api/saved", params={"limit": 0})


@scenario("PUT /api/saved/{otodom_id}", "saved_with_note", 200)
async def save(w: World) -> Exchange:
    who = await w.user(label="saved")
    ref = (await w.seed_audits(who, 1))[0]
    return await w.send(who, "PUT", f"/api/saved/{ref}", json={"note": "Warto zadzwonić"})


@scenario("PUT /api/saved/{otodom_id}", "saved_without_note", 200)
async def save_plain(w: World) -> Exchange:
    who = await w.user(label="saved")
    ref = (await w.seed_audits(who, 1))[0]
    return await w.send(who, "PUT", f"/api/saved/{ref}", json={})


@scenario("PUT /api/saved/{otodom_id}", "limit_reached", 409, "500 saved listings per user")
async def save_limit(w: World) -> Exchange:
    who = await w.user(label="saved")
    refs = await w.seed_audits(who, 501)  # newest first
    await w.sql(
        "INSERT INTO app.saved_listing (user_id, otodom_id) SELECT user_id, otodom_id FROM app.audit"
        " WHERE user_id = :u AND otodom_id <> :r",
        u=who.user_id,
        r=refs[0],
    )
    return await w.send(who, "PUT", f"/api/saved/{refs[0]}", json={})


@scenario("PUT /api/saved/{otodom_id}", "never_audited", 404, "also what another user's listing looks like")
async def save_unknown(w: World) -> Exchange:
    return await w.send(await w.user(label="saved"), "PUT", "/api/saved/ID00000000", json={})


@scenario("PUT /api/saved/{otodom_id}", "note_too_long", 422)
async def save_long(w: World) -> Exchange:
    who = await w.user(label="saved")
    ref = (await w.seed_audits(who, 1))[0]
    return await w.send(who, "PUT", f"/api/saved/{ref}", json={"note": "x" * 2001})


@scenario("PUT /api/saved/{otodom_id}", "bad_id", 422)
async def save_bad_id(w: World) -> Exchange:
    return await w.send(await w.user(label="saved"), "PUT", "/api/saved/no", json={})


@scenario("DELETE /api/saved/{otodom_id}", "unsaved", 204)
async def unsave(w: World) -> Exchange:
    who = await w.user(label="saved")
    ref = (await w.seed_audits(who, 1))[0]
    await w.send(who, "PUT", f"/api/saved/{ref}", json={})
    return await w.send(who, "DELETE", f"/api/saved/{ref}")


@scenario("DELETE /api/saved/{otodom_id}", "not_saved", 204, "idempotent")
async def unsave_again(w: World) -> Exchange:
    return await w.send(await w.user(label="saved"), "DELETE", "/api/saved/ID00000000")


@scenario("DELETE /api/saved/{otodom_id}", "bad_id", 422)
async def unsave_bad_id(w: World) -> Exchange:
    return await w.send(await w.user(label="saved"), "DELETE", "/api/saved/no")


# =============================================================================================== audits
@scenario("POST /api/audits", "accepted", 202)
async def audit_accepted(w: World) -> Exchange:
    who = await w.user(label="audit")
    ref = w.serve_sale(SUCCESS[0])
    accepted = await w.submit(who, f"https://www.otodom.pl/pl/oferta/mieszkanie-{ref}")
    await w.run_worker()
    return accepted


@scenario("POST /api/audits", "accepted_by_short_id", 202)
async def audit_accepted_id(w: World) -> Exchange:
    who = await w.user(label="audit")
    ref = w.serve_sale(SUCCESS[1])
    accepted = await w.submit(who, ref, lang="en")
    await w.run_worker()
    return accepted


@scenario("POST /api/audits", "invalid_listing_ref", 422)
async def audit_bad_ref(w: World) -> Exchange:
    return await w.submit(await w.user(label="audit"), "https://example.com/not-otodom")


@scenario("POST /api/audits", "no_credits", 402)
async def audit_no_credits(w: World) -> Exchange:
    return await w.submit(await w.user(label="broke", credits=0), w.serve_sale(SUCCESS[0]))


@scenario("POST /api/audits", "already_in_progress", 409)
async def audit_in_progress(w: World) -> Exchange:
    who = await w.user(label="audit")
    ref = w.serve_sale(SUCCESS[2])
    first = await w.submit(who, ref)
    assert first.status == 202, first.body
    second = await w.submit(who, ref)
    await w.run_worker()
    return second


@scenario("POST /api/audits", "analyst_not_available", 403)
async def audit_analyst(w: World) -> Exchange:
    return await w.submit(await w.user(label="audit"), w.serve_sale(SUCCESS[0]), analyst=True)


@scenario("POST /api/audits", "billing_hold", 403)
async def audit_hold(w: World) -> Exchange:
    who = await w.user(label="hold")
    await w.sql(
        "UPDATE app.credit_account SET billing_hold = 'purchase_reversed' WHERE user_id = :u", u=who.user_id
    )
    return await w.submit(who, w.serve_sale(SUCCESS[0]))


@scenario("POST /api/audits", "unknown_field", 422)
async def audit_unknown_field(w: World) -> Exchange:
    return await w.send(
        await w.user(label="audit"), "POST", "/api/audits", json={"listing_ref": "ID12345678", "x": 1}
    )


@scenario("GET /api/audits", "empty", 200)
async def audits_empty(w: World) -> Exchange:
    return await w.send(await w.user(label="list"), "GET", "/api/audits")


@scenario("GET /api/audits", "after_real_runs", 200)
async def audits_real(w: World) -> Exchange:
    who = await w.user(label="list", credits=5)
    for listing in SUCCESS[:3]:
        await w.submit(who, w.serve_sale(listing))
    await w.run_worker()
    return await w.send(who, "GET", "/api/audits")


@scenario("GET /api/audits", "heavy_user_default_page", 200, "120 audits: only the newest 50 come back")
async def audits_many(w: World) -> Exchange:
    who = await w.user(label="heavy")
    await w.seed_audits(who, 120)
    return await w.send(who, "GET", "/api/audits")


@scenario("GET /api/audits", "heavy_user_limit_100", 200)
async def audits_limit(w: World) -> Exchange:
    who = await w.user(label="heavy")
    await w.seed_audits(who, 120)
    return await w.send(who, "GET", "/api/audits", params={"limit": 100})


@scenario("GET /api/audits", "second_page_by_cursor", 200)
async def audits_second_page(w: World) -> Exchange:
    who = await w.user(label="heavy")
    await w.seed_audits(who, 120)
    first = await w.send(who, "GET", "/api/audits", params={"limit": 50})
    return await w.send(who, "GET", "/api/audits", params={"limit": 50, "cursor": first.body["next_cursor"]})


@scenario("GET /api/audits", "last_page_has_no_cursor", 200)
async def audits_last_page(w: World) -> Exchange:
    who = await w.user(label="heavy")
    await w.seed_audits(who, 120)
    cursor = None
    for _ in range(2):
        page = await w.send(
            who, "GET", "/api/audits", params={"limit": 50, **({"cursor": cursor} if cursor else {})}
        )
        cursor = page.body["next_cursor"]
    return await w.send(who, "GET", "/api/audits", params={"limit": 50, "cursor": cursor})


@scenario("GET /api/audits", "filtered_by_status", 200)
async def audits_filtered(w: World) -> Exchange:
    who = await w.user(label="heavy")
    await w.seed_audits(who, 40)
    return await w.send(
        who, "GET", "/api/audits", params=[("status", "failed_input"), ("status", "rejected")]
    )


@scenario("GET /api/audits", "filtered_with_nothing_found", 200)
async def audits_filtered_empty(w: World) -> Exchange:
    who = await w.user(label="heavy")
    await w.seed_audits(who, 5)
    return await w.send(who, "GET", "/api/audits", params={"q": "ZZZZ"})


@scenario("GET /api/audits", "invalid_cursor", 422)
async def audits_bad_cursor(w: World) -> Exchange:
    return await w.send(await w.user(label="list"), "GET", "/api/audits", params={"cursor": "garbage"})


@scenario("GET /api/audits", "validation_error", 422)
async def audits_validation(w: World) -> Exchange:
    return await w.send(await w.user(label="list"), "GET", "/api/audits", params={"limit": 101})


def _succeeded(index: int) -> Run:
    async def run(w: World) -> Exchange:
        who = await w.user(label="report")
        audit_id = await w.audit_to_end(who, w.serve_sale(SUCCESS[index]))
        return await w.send(who, "GET", f"/api/audits/{audit_id}")

    return run


for _i, _listing in enumerate(SUCCESS):
    SCENARIOS.append(
        Scenario("GET /api/audits/{audit_id}", f"succeeded_{_listing.key}", 200, run=_succeeded(_i))
    )


@scenario("GET /api/audits/{audit_id}", "succeeded_degraded", 200, "no vision answer: the engine says so")
async def audit_degraded(w: World) -> Exchange:
    who = await w.user(label="report")
    audit_id = await w.audit_to_end(who, w.serve_sale(SUCCESS[3], with_vision=False))
    return await w.send(who, "GET", f"/api/audits/{audit_id}")


@scenario("GET /api/audits/{audit_id}", "rejected_rent_is_not_a_deal", 200)
async def audit_rent(w: World) -> Exchange:
    who = await w.user(label="report")
    audit_id = await w.audit_to_end(who, w.serve(RENT_AD))
    return await w.send(who, "GET", f"/api/audits/{audit_id}")


@scenario("GET /api/audits/{audit_id}", "rejected_fractional_ownership", 200)
async def audit_fractional(w: World) -> Exchange:
    who = await w.user(label="report")
    audit_id = await w.audit_to_end(who, w.serve(FRACTIONAL_AD))
    return await w.send(who, "GET", f"/api/audits/{audit_id}")


@scenario("GET /api/audits/{audit_id}", "failed_upstream_blocked", 200)
async def audit_blocked(w: World) -> Exchange:
    who = await w.user(label="report")
    audit_id = await w.audit_to_end(who, w.serve(UpstreamBlocked("captcha", retryable=False)))
    return await w.send(who, "GET", f"/api/audits/{audit_id}")


@scenario("GET /api/audits/{audit_id}", "failed_input_listing_gone", 200)
async def audit_gone(w: World) -> Exchange:
    who = await w.user(label="report")
    audit_id = await w.audit_to_end(who, w.serve(ListingGone("404")))
    return await w.send(who, "GET", f"/api/audits/{audit_id}")


@scenario("GET /api/audits/{audit_id}", "queued_not_yet_run", 200)
async def audit_queued(w: World) -> Exchange:
    who = await w.user(label="report")
    accepted = await w.submit(who, w.serve_sale(SUCCESS[0]))
    got = await w.send(who, "GET", f"/api/audits/{accepted.body['audit_id']}")
    await w.run_worker()
    return got


@scenario("GET /api/audits/{audit_id}", "foreign_audit", 404, "another user's audit is a 404, never a 403")
async def audit_foreign(w: World) -> Exchange:
    owner, other = await w.user(label="owner"), await w.user(label="other")
    audit_id = await w.audit_to_end(owner, w.serve_sale(SUCCESS[0]))
    return await w.send(other, "GET", f"/api/audits/{audit_id}")


@scenario("GET /api/audits/{audit_id}", "unknown_audit", 404)
async def audit_unknown(w: World) -> Exchange:
    return await w.send(await w.user(label="report"), "GET", f"/api/audits/{uuid4()}")


@scenario("GET /api/audits/{audit_id}", "malformed_id", 422)
async def audit_malformed(w: World) -> Exchange:
    return await w.send(await w.user(label="report"), "GET", "/api/audits/not-a-uuid")


@scenario("GET /api/audits/{audit_id}/events", "success_transcript", 200)
async def events_success(w: World) -> Exchange:
    who = await w.user(label="events")
    audit_id = await w.audit_to_end(who, w.serve_sale(SUCCESS[0]))
    return await w.send(who, "GET", f"/api/audits/{audit_id}/events")


@scenario("GET /api/audits/{audit_id}/events", "rejected_transcript", 200)
async def events_rejected(w: World) -> Exchange:
    who = await w.user(label="events")
    audit_id = await w.audit_to_end(who, w.serve(RENT_AD))
    return await w.send(who, "GET", f"/api/audits/{audit_id}/events")


@scenario("GET /api/audits/{audit_id}/events", "failure_transcript", 200)
async def events_failed(w: World) -> Exchange:
    who = await w.user(label="events")
    audit_id = await w.audit_to_end(who, w.serve(UpstreamBlocked("captcha", retryable=False)))
    return await w.send(who, "GET", f"/api/audits/{audit_id}/events")


@scenario("GET /api/audits/{audit_id}/events", "resume_after_last_event", 200)
async def events_resume(w: World) -> Exchange:
    who = await w.user(label="events")
    audit_id = await w.audit_to_end(who, w.serve_sale(SUCCESS[1]))
    whole = await w.send(who, "GET", f"/api/audits/{audit_id}/events")
    first_id = next(line.split(": ", 1)[1] for line in whole.body.splitlines() if line.startswith("id: "))
    return await w.send(who, "GET", f"/api/audits/{audit_id}/events", headers={"Last-Event-ID": first_id})


@scenario("GET /api/audits/{audit_id}/events", "foreign_audit", 404)
async def events_foreign(w: World) -> Exchange:
    owner, other = await w.user(label="owner"), await w.user(label="other")
    audit_id = await w.audit_to_end(owner, w.serve_sale(SUCCESS[0]))
    return await w.send(other, "GET", f"/api/audits/{audit_id}/events")


@scenario("GET /api/audits/{audit_id}/events", "malformed_id", 422)
async def events_malformed(w: World) -> Exchange:
    return await w.send(await w.user(label="events"), "GET", "/api/audits/not-a-uuid/events")


# ============================================================================================== billing
@scenario("GET /api/billing/packs", "three_packs", 200)
async def packs(w: World) -> Exchange:
    return await w.send(await w.user(label="shop"), "GET", "/api/billing/packs")


@scenario("GET /api/billing/packs", "billing_disabled", 200)
async def packs_disabled(w: World) -> Exchange:
    who = await w.user(label="shop")
    async with w.billing_disabled():
        return await w.send(who, "GET", "/api/billing/packs")


@scenario("POST /api/billing/checkout", "created", 200)
async def checkout(w: World) -> Exchange:
    return await w.buy(await w.user(label="buyer"), "reports_5")


@scenario("POST /api/billing/checkout", "same_key_replays_the_purchase", 200)
async def checkout_replay(w: World) -> Exchange:
    who, key = await w.user(label="buyer"), uuid4()
    await w.buy(who, "reports_1", key)
    return await w.buy(who, "reports_1", key)


@scenario("POST /api/billing/checkout", "provider_outcome_unknown", 202, "Paddle timed out after creating")
async def checkout_unknown(w: World) -> Exchange:
    who = await w.user(label="buyer")
    w.paddle.fail_create_after_store = True
    try:
        return await w.buy(who, "reports_10")
    finally:
        w.paddle.fail_create_after_store = False


@scenario("POST /api/billing/checkout", "key_reused_for_another_pack", 409)
async def checkout_conflict(w: World) -> Exchange:
    who, key = await w.user(label="buyer"), uuid4()
    await w.buy(who, "reports_1", key)
    return await w.buy(who, "reports_5", key)


@scenario("POST /api/billing/checkout", "unknown_pack", 422)
async def checkout_unknown_pack(w: World) -> Exchange:
    return await w.buy(await w.user(label="buyer"), "reports_99")


@scenario("POST /api/billing/checkout", "missing_idempotency_key", 422)
async def checkout_no_key(w: World) -> Exchange:
    return await w.send(
        await w.user(label="buyer"), "POST", "/api/billing/checkout", json={"pack_code": "reports_5"}
    )


@scenario("POST /api/billing/checkout", "billing_disabled", 503)
async def checkout_disabled(w: World) -> Exchange:
    who = await w.user(label="buyer")
    async with w.billing_disabled():
        return await w.buy(who)


@scenario("POST /api/billing/checkout", "email_not_verified", 403)
async def checkout_unverified(w: World) -> Exchange:
    return await w.buy(await w.user(label="buyer", verified=False))


@scenario("POST /api/billing/checkout", "billing_hold", 403)
async def checkout_hold(w: World) -> Exchange:
    who = await w.user(label="buyer")
    await w.sql(
        "UPDATE app.credit_account SET billing_hold = 'purchase_reversed' WHERE user_id = :u", u=who.user_id
    )
    return await w.buy(who)


@scenario("POST /api/billing/checkout", "provider_refused", 502)
async def checkout_refused(w: World) -> Exchange:
    who = await w.user(label="buyer")
    original = w.paddle.create_transaction

    async def refuse(**_: Any) -> Any:
        raise PaddleError("refused")

    w.paddle.create_transaction = refuse
    try:
        return await w.buy(who)
    finally:
        w.paddle.create_transaction = original


@scenario("POST /api/billing/checkout", "rate_limited", 429)
async def checkout_limited(w: World) -> Exchange:
    who = await w.user(label="buyer")
    last = await w.buy(who)
    for _ in range(5):
        last = await w.buy(who)
    return last


@scenario("GET /api/billing/purchases", "empty", 200)
async def purchases_empty(w: World) -> Exchange:
    return await w.send(await w.user(label="buyer"), "GET", "/api/billing/purchases")


@scenario("GET /api/billing/purchases", "created_granted_and_refunded", 200)
async def purchases_mixed(w: World) -> Exchange:
    who, admin = await w.user(label="buyer", credits=0), await w.user(label="admin", role="admin")
    await w.buy(who, "reports_1")  # started, never paid
    await w.bought(who, "reports_5")
    refunded = await w.bought(who, "reports_10")
    requested = await w.send(
        admin,
        "POST",
        f"/api/admin/billing/purchases/{refunded['purchase_id']}/refund",
        json={"reason": "buyer asked within 14 days, pack unused"},
    )
    assert requested.status == 202, requested.body
    await w.approve_refund(refunded["transaction_id"], requested.body["adjustment_id"])
    return await w.send(who, "GET", "/api/billing/purchases")


@scenario("GET /api/billing/purchases", "by_request_key", 200)
async def purchases_by_key(w: World) -> Exchange:
    who = await w.user(label="buyer")
    key = uuid4()
    await w.buy(who, "reports_5", key)
    await w.buy(who, "reports_1")  # another order, not returned
    return await w.send(who, "GET", "/api/billing/purchases", params={"request_key": str(key)})


@scenario("GET /api/billing/purchases", "validation_error", 422)
async def purchases_validation(w: World) -> Exchange:
    return await w.send(await w.user(label="buyer"), "GET", "/api/billing/purchases", params={"limit": 0})


@scenario("GET /api/billing/purchases/{purchase_id}", "granted", 200)
async def purchase_granted(w: World) -> Exchange:
    who = await w.user(label="buyer", credits=0)
    bought = await w.bought(who, "reports_5")
    return await w.send(who, "GET", f"/api/billing/purchases/{bought['purchase_id']}")


@scenario("GET /api/billing/purchases/{purchase_id}", "checkout_started", 200)
async def purchase_created(w: World) -> Exchange:
    who = await w.user(label="buyer")
    created = await w.buy(who, "reports_1")
    return await w.send(who, "GET", f"/api/billing/purchases/{created.body['purchase_id']}")


@scenario("GET /api/billing/purchases/{purchase_id}", "foreign_purchase", 404)
async def purchase_foreign(w: World) -> Exchange:
    owner, other = await w.user(label="buyer"), await w.user(label="other")
    created = await w.buy(owner, "reports_1")
    return await w.send(other, "GET", f"/api/billing/purchases/{created.body['purchase_id']}")


@scenario("GET /api/billing/purchases/{purchase_id}", "malformed_id", 422)
async def purchase_malformed(w: World) -> Exchange:
    return await w.send(await w.user(label="buyer"), "GET", "/api/billing/purchases/nope")


@scenario("GET /api/billing/purchases/{purchase_id}/invoice", "granted", 200)
async def invoice(w: World) -> Exchange:
    who = await w.user(label="buyer", credits=0)
    bought = await w.bought(who, "reports_5")
    return await w.send(who, "GET", f"/api/billing/purchases/{bought['purchase_id']}/invoice")


@scenario("GET /api/billing/purchases/{purchase_id}/invoice", "not_paid_yet", 409)
async def invoice_unpaid(w: World) -> Exchange:
    who = await w.user(label="buyer")
    created = await w.buy(who, "reports_1")
    return await w.send(who, "GET", f"/api/billing/purchases/{created.body['purchase_id']}/invoice")


@scenario("GET /api/billing/purchases/{purchase_id}/invoice", "provider_outage", 502)
async def invoice_outage(w: World) -> Exchange:
    who = await w.user(label="buyer", credits=0)
    bought = await w.bought(who, "reports_1")
    original = w.paddle.get_invoice_url

    async def down(transaction_id: str) -> str:
        raise PaddleError("down")

    w.paddle.get_invoice_url = down
    try:
        return await w.send(who, "GET", f"/api/billing/purchases/{bought['purchase_id']}/invoice")
    finally:
        w.paddle.get_invoice_url = original


@scenario("GET /api/billing/purchases/{purchase_id}/invoice", "foreign_purchase", 404)
async def invoice_foreign(w: World) -> Exchange:
    owner, other = await w.user(label="buyer", credits=0), await w.user(label="other")
    bought = await w.bought(owner, "reports_1")
    return await w.send(other, "GET", f"/api/billing/purchases/{bought['purchase_id']}/invoice")


@scenario("GET /api/billing/purchases/{purchase_id}/invoice", "billing_disabled", 503)
async def invoice_disabled(w: World) -> Exchange:
    who = await w.user(label="buyer")
    async with w.billing_disabled():
        return await w.send(who, "GET", f"/api/billing/purchases/{uuid4()}/invoice")


@scenario("GET /api/billing/purchases/{purchase_id}/invoice", "malformed_id", 422)
async def invoice_malformed(w: World) -> Exchange:
    return await w.send(await w.user(label="buyer"), "GET", "/api/billing/purchases/nope/invoice")


# =============================================================================================== admin
@scenario("GET /api/admin/flags", "three_flags", 200)
async def flags(w: World) -> Exchange:
    await w.add_flag("smoke_everyone", description="on for everyone", enabled_default=True)
    await w.add_flag("smoke_pro_only", description="pro plan only", enabled_default=True, min_plan="pro")
    await w.add_flag("smoke_half_rolled_out", description="half rolled out", rollout_pct=50)
    return await w.send(await w.user(label="admin", role="admin"), "GET", "/api/admin/flags")


@scenario("PUT /api/admin/flags/{key}", "updated", 200)
async def flag_update(w: World) -> Exchange:
    key = await w.add_flag("smoke_rollout", description="rollout", rollout_pct=10)
    admin = await w.user(label="admin", role="admin")
    return await w.send(
        admin, "PUT", f"/api/admin/flags/{key}", json={"rollout_pct": 75, "enabled_default": True}
    )


@scenario("PUT /api/admin/flags/{key}", "min_plan_cleared", 200)
async def flag_clear_plan(w: World) -> Exchange:
    key = await w.add_flag("smoke_min_plan", description="pro", min_plan="pro")
    admin = await w.user(label="admin", role="admin")
    return await w.send(admin, "PUT", f"/api/admin/flags/{key}", json={"clear_min_plan": True})


@scenario("PUT /api/admin/flags/{key}", "unknown_flag", 404)
async def flag_unknown(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(admin, "PUT", "/api/admin/flags/does_not_exist", json={"enabled_default": True})


@scenario("PUT /api/admin/flags/{key}", "rollout_out_of_range", 422)
async def flag_range(w: World) -> Exchange:
    key = await w.add_flag("smoke_range", description="rollout")
    admin = await w.user(label="admin", role="admin")
    return await w.send(admin, "PUT", f"/api/admin/flags/{key}", json={"rollout_pct": 101})


@scenario("PUT /api/admin/flags/{key}/overrides/{user_id}", "override_set", 200)
async def override_put(w: World) -> Exchange:
    key = await w.add_flag("smoke_override_set", description="beta")
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    return await w.send(
        admin,
        "PUT",
        f"/api/admin/flags/{key}/overrides/{target.user_id}",
        json={"enabled": True, "reason": "design partner"},
    )


@scenario("PUT /api/admin/flags/{key}/overrides/{user_id}", "unknown_user", 404)
async def override_unknown(w: World) -> Exchange:
    key = await w.add_flag("smoke_override_unknown", description="beta")
    admin = await w.user(label="admin", role="admin")
    return await w.send(
        admin,
        "PUT",
        f"/api/admin/flags/{key}/overrides/no-such-user",
        json={"enabled": True, "reason": "design partner"},
    )


@scenario("PUT /api/admin/flags/{key}/overrides/{user_id}", "reason_too_short", 422)
async def override_short(w: World) -> Exchange:
    key = await w.add_flag("smoke_override_short", description="beta")
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    return await w.send(
        admin,
        "PUT",
        f"/api/admin/flags/{key}/overrides/{target.user_id}",
        json={"enabled": True, "reason": "x"},
    )


@scenario("DELETE /api/admin/flags/{key}/overrides/{user_id}", "override_removed", 204)
async def override_delete(w: World) -> Exchange:
    key = await w.add_flag("smoke_override_removed", description="beta")
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    path = f"/api/admin/flags/{key}/overrides/{target.user_id}"
    await w.send(admin, "PUT", path, json={"enabled": True, "reason": "design partner"})
    return await w.send(admin, "DELETE", path)


@scenario("DELETE /api/admin/flags/{key}/overrides/{user_id}", "no_such_override", 204, "idempotent")
async def override_delete_again(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(admin, "DELETE", "/api/admin/flags/none_here/overrides/nobody")


@scenario("DELETE /api/admin/flags/{key}/overrides/{user_id}", "malformed_key", 422)
async def override_delete_malformed(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(admin, "DELETE", "/api/admin/flags/BAD-KEY/overrides/nobody")


@scenario("POST /api/admin/credits/adjust", "applied", 200)
async def adjust(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target", credits=2)
    return await w.send(
        admin,
        "POST",
        "/api/admin/credits/adjust",
        json={"user_id": target.user_id, "delta": 3, "note": "goodwill", "idempotency_key": str(uuid4())},
    )


@scenario("POST /api/admin/credits/adjust", "repeat_changes_nothing", 200)
async def adjust_repeat(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target", credits=2)
    body = {"user_id": target.user_id, "delta": 3, "note": "goodwill", "idempotency_key": str(uuid4())}
    await w.send(admin, "POST", "/api/admin/credits/adjust", json=body)
    return await w.send(admin, "POST", "/api/admin/credits/adjust", json=body)


@scenario("POST /api/admin/credits/adjust", "would_go_below_zero", 409)
async def adjust_below_zero(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target", credits=1)
    return await w.send(
        admin,
        "POST",
        "/api/admin/credits/adjust",
        json={"user_id": target.user_id, "delta": -5, "note": "claw back", "idempotency_key": str(uuid4())},
    )


@scenario("POST /api/admin/credits/adjust", "unknown_user", 404)
async def adjust_unknown(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(
        admin,
        "POST",
        "/api/admin/credits/adjust",
        json={"user_id": "nobody", "delta": 1, "note": "goodwill", "idempotency_key": str(uuid4())},
    )


@scenario("POST /api/admin/credits/adjust", "zero_delta", 422)
async def adjust_zero(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    return await w.send(
        admin,
        "POST",
        "/api/admin/credits/adjust",
        json={"user_id": target.user_id, "delta": 0, "note": "nothing", "idempotency_key": str(uuid4())},
    )


@scenario("POST /api/admin/users/{user_id}/billing-hold/clear", "cleared", 200)
async def hold_clear(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    await w.sql(
        "UPDATE app.credit_account SET billing_hold = 'purchase_reversed' WHERE user_id = :u",
        u=target.user_id,
    )
    return await w.send(
        admin,
        "POST",
        f"/api/admin/users/{target.user_id}/billing-hold/clear",
        json={"note": "reviewed with the buyer, units were used"},
    )


@scenario("POST /api/admin/users/{user_id}/billing-hold/clear", "no_hold_to_clear", 200)
async def hold_clear_none(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    return await w.send(
        admin,
        "POST",
        f"/api/admin/users/{target.user_id}/billing-hold/clear",
        json={"note": "checking there is nothing"},
    )


@scenario("POST /api/admin/users/{user_id}/billing-hold/clear", "unknown_user", 404)
async def hold_clear_unknown(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(
        admin, "POST", "/api/admin/users/nobody/billing-hold/clear", json={"note": "checking this out"}
    )


@scenario("POST /api/admin/users/{user_id}/billing-hold/clear", "note_too_short", 422)
async def hold_clear_short(w: World) -> Exchange:
    admin, target = await w.user(label="admin", role="admin"), await w.user(label="target")
    return await w.send(
        admin, "POST", f"/api/admin/users/{target.user_id}/billing-hold/clear", json={"note": "ok"}
    )


@scenario("GET /api/admin/jobs", "counts_and_recent", 200)
async def jobs(w: World) -> Exchange:
    who = await w.user(label="jobs")
    await w.audit_to_end(who, w.serve_sale(SUCCESS[0]))
    return await w.send(await w.user(label="admin", role="admin"), "GET", "/api/admin/jobs")


@scenario("GET /api/admin/jobs", "filtered_by_queue_and_status", 200)
async def jobs_filtered(w: World) -> Exchange:
    who = await w.user(label="jobs")
    await w.audit_to_end(who, w.serve_sale(SUCCESS[1]))
    return await w.send(
        await w.user(label="admin", role="admin"),
        "GET",
        "/api/admin/jobs",
        params={"queue": "audit", "status": "succeeded", "limit": 5},
    )


@scenario("GET /api/admin/jobs", "bad_queue_name", 422)
async def jobs_invalid(w: World) -> Exchange:
    return await w.send(
        await w.user(label="admin", role="admin"), "GET", "/api/admin/jobs", params={"queue": "NOT OK"}
    )


@scenario(
    "POST /api/admin/billing/purchases/{purchase_id}/refund", "requested", 202, "documented as 200 only"
)
async def refund(w: World) -> Exchange:
    who, admin = await w.user(label="buyer", credits=0), await w.user(label="admin", role="admin")
    bought = await w.bought(who, "reports_5")
    return await w.send(
        admin,
        "POST",
        f"/api/admin/billing/purchases/{bought['purchase_id']}/refund",
        json={"reason": "buyer asked within 14 days, pack unused"},
    )


@scenario("POST /api/admin/billing/purchases/{purchase_id}/refund", "provider_refused", 502)
async def refund_refused(w: World) -> Exchange:
    who, admin = await w.user(label="buyer", credits=0), await w.user(label="admin", role="admin")
    bought = await w.bought(who, "reports_1")
    original = w.paddle.create_full_refund

    async def refuse(**_: Any) -> Any:
        raise PaddleError("refused")

    w.paddle.create_full_refund = refuse
    try:
        return await w.send(
            admin,
            "POST",
            f"/api/admin/billing/purchases/{bought['purchase_id']}/refund",
            json={"reason": "buyer asked within 14 days, pack unused"},
        )
    finally:
        w.paddle.create_full_refund = original


@scenario("POST /api/admin/billing/purchases/{purchase_id}/refund", "not_refundable", 409)
async def refund_unknown(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(
        admin,
        "POST",
        f"/api/admin/billing/purchases/{uuid4()}/refund",
        json={"reason": "buyer asked within 14 days, pack unused"},
    )


@scenario("POST /api/admin/billing/purchases/{purchase_id}/refund", "reason_too_short", 422)
async def refund_short(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    return await w.send(admin, "POST", f"/api/admin/billing/purchases/{uuid4()}/refund", json={"reason": "x"})


@scenario("POST /api/admin/billing/purchases/{purchase_id}/refund", "billing_disabled", 503)
async def refund_disabled(w: World) -> Exchange:
    admin = await w.user(label="admin", role="admin")
    async with w.billing_disabled():
        return await w.send(
            admin,
            "POST",
            f"/api/admin/billing/purchases/{uuid4()}/refund",
            json={"reason": "buyer asked within 14 days, pack unused"},
        )


# ============================================================================== generated: no session
def unauthenticated(key: str, path: str) -> Run:
    """The same call with no cookie: every non-public operation answers 401 `UNAUTHENTICATED`."""
    method = key.split(" ", 1)[0]

    async def run(w: World) -> Exchange:
        anon: Actor = w.anonymous()
        return await w.send(anon, method, path, json={} if method in {"POST", "PUT", "DELETE"} else None)

    return run


def wrong_origin(key: str, path: str) -> Run:
    """An unsafe call whose Origin is not ours: refused before anything else (CSRF defence)."""
    method = key.split(" ", 1)[0]

    async def run(w: World) -> Exchange:
        return await w.send(w.anonymous(origin="https://evil.test"), method, path, json={})

    return run


def not_an_admin(key: str, path: str) -> Run:
    """A signed-in user without the admin role: 403 `ADMIN_ONLY`, never a hint that the resource exists."""
    method = key.split(" ", 1)[0]

    async def run(w: World) -> Exchange:
        body = {} if method in {"POST", "PUT", "DELETE"} else None
        return await w.send(await w.user(label="plain"), method, path, json=body)

    return run


# The operations that answer without a session. Every other operation also gets the generated `no_session`
# scenario below (401 `UNAUTHENTICATED`).
PUBLIC = frozenset(
    {
        "POST /api/auth/google",
        "POST /api/auth/email/start",
        "POST /api/auth/email/verify",
        "POST /api/auth/register",
        "POST /api/auth/register/resend",
        "POST /api/auth/register/verify",
        "POST /api/auth/login",
        "POST /api/auth/password/forgot",
        "POST /api/auth/password/reset",
        "POST /api/auth/signout",
    }
)
PATH_VALUES = {
    "audit_id": "00000000-0000-4000-8000-000000000001",
    "purchase_id": "00000000-0000-4000-8000-000000000002",
    "otodom_id": "ID00000000",
    "key": "some_flag",
    "user_id": "nobody",
}


def all_scenarios() -> list[Scenario]:
    """The hand-written scenarios plus one `no_session` scenario for every operation that needs a session."""
    from contract import load_spec, operations  # noqa: PLC0415

    generated: list[Scenario] = []
    for key, op in operations(load_spec()).items():
        path = op.path.format(**PATH_VALUES)
        method = key.split(" ", 1)[0]
        if key not in PUBLIC:
            generated.append(Scenario(key, "no_session", 401, unauthenticated(key, path)))
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            generated.append(Scenario(key, "wrong_origin", 403, wrong_origin(key, path)))
        if op.path.startswith("/api/admin/"):
            generated.append(Scenario(key, "not_an_admin", 403, not_an_admin(key, path)))
    return [*SCENARIOS, *generated]
