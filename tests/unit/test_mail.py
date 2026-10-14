"""Magic-link mail: content, retries, provider errors and the production guards."""

from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr
from rm_core.settings import Settings
from rm_worker.clients.resend import (
    LogMailer,
    MailError,
    PermanentMailError,
    ResendMailer,
    TransientMailError,
    is_onboarding_sender,
)
from rm_worker.tasks.email import build_mailer, deliver_magic_link, magic_link_message

URL = "https://app.example.test/login/email#t=abcDEF123_-"


def test_the_message_has_one_link_in_both_parts_and_no_tracking() -> None:
    m = magic_link_message("a@example.test", URL, 30)
    assert URL in m.text
    assert m.html.count("href=") == 1
    assert "30 minut" in m.text
    assert "<img" not in m.html
    assert m.to == "a@example.test"


def test_the_product_name_comes_from_app_name() -> None:
    m = magic_link_message("a@example.test", URL, 30, "Acme")
    assert "Acme" in m.subject
    assert "Acme" in m.text
    assert "Acme" in m.html
    assert "RentMonitor" not in m.subject + m.text + m.html
    assert "Renti" in magic_link_message("a@example.test", URL, 30).subject


def test_sender_and_osm_agent_follow_app_name() -> None:
    s = Settings(_env_file=None, app_name="Acme", mail_from="", nominatim_user_agent="")  # type: ignore[call-arg]
    assert s.mail_sender == "Acme <onboarding@resend.dev>"
    assert s.osm_user_agent == "Acme/1.0 (set-an-ops-contact)"
    s = Settings(_env_file=None, app_name="Acme", mail_from="no-reply@x.test")  # type: ignore[call-arg]
    assert s.mail_sender == "Acme <no-reply@x.test>"
    s = Settings(_env_file=None, mail_from="Other <no-reply@x.test>")  # type: ignore[call-arg]
    assert s.mail_sender == "Other <no-reply@x.test>"
    assert Settings(_env_file=None).app_name == "Renti"  # type: ignore[call-arg]


def test_html_is_escaped() -> None:
    m = magic_link_message("a@example.test", 'https://x.test/"><script>alert(1)</script>', 30)
    assert "<script>" not in m.html


def test_the_idempotency_key_is_stable_per_recipient_and_link() -> None:
    a = magic_link_message("a@example.test", URL, 30).idempotency_key
    assert a == magic_link_message("a@example.test", URL, 30).idempotency_key
    assert a != magic_link_message("b@example.test", URL, 30).idempotency_key
    assert a != magic_link_message("a@example.test", URL + "x", 30).idempotency_key


@pytest.mark.parametrize(
    ("sender", "expected"),
    [
        ("RentMonitor <onboarding@resend.dev>", True),
        ("onboarding@RESEND.DEV", True),
        ("RentMonitor <no-reply@rentmonitor.pl>", False),
        ("x@notresend.dev.example.test", False),
    ],
)
def test_the_onboarding_sender_is_recognised(sender: str, expected: bool) -> None:
    assert is_onboarding_sender(sender) is expected


def test_production_refuses_the_onboarding_sender_and_a_missing_key() -> None:
    http = httpx.AsyncClient()
    with pytest.raises(MailError) as no_key:
        build_mailer(Settings(app_env="production"), http)
    assert no_key.value.permanent
    keyed = Settings(
        app_env="production",
        resend_api_key=SecretStr("re_x"),
        mail_from="RentMonitor <onboarding@resend.dev>",
    )
    with pytest.raises(MailError) as onboarding:
        build_mailer(keyed, http)
    assert onboarding.value.permanent
    verified = Settings(
        app_env="production",
        resend_api_key=SecretStr("re_x"),
        mail_from="RentMonitor <no-reply@rentmonitor.pl>",
    )
    assert isinstance(build_mailer(verified, http), ResendMailer)


def test_development_without_a_key_logs_instead_of_sending() -> None:
    assert isinstance(build_mailer(Settings(app_env="development"), httpx.AsyncClient()), LogMailer)


async def test_the_dev_mailer_records_the_message() -> None:
    mailer = LogMailer()
    await deliver_magic_link(mailer, Settings(app_env="development"), "a@example.test", URL)
    assert len(mailer.sent) == 1


def mailer(handler: object) -> ResendMailer:
    return ResendMailer(
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),  # type: ignore[arg-type]
        "re_secret_key",
        "RentMonitor <no-reply@rentmonitor.pl>",
    )


async def test_resend_receives_the_expected_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "abc"})

    msg = magic_link_message("a@example.test", URL, 30)
    await mailer(handler).send(msg)
    request = seen[0]
    assert request.url == "https://api.resend.com/emails"
    assert request.headers["authorization"] == "Bearer re_secret_key"
    assert request.headers["idempotency-key"] == msg.idempotency_key
    body = request.read().decode()
    assert '"to":["a@example.test"]' in body.replace(" ", "")


@pytest.mark.parametrize(
    ("status", "permanent"), [(429, False), (500, False), (503, False), (401, True), (422, True)]
)
async def test_provider_errors_are_classified_for_the_retry_policy(status: int, permanent: bool) -> None:
    with pytest.raises(MailError) as err:
        await mailer(lambda r: httpx.Response(status)).send(magic_link_message("a@example.test", URL, 30))
    assert err.value.permanent is permanent
    assert "re_secret_key" not in str(err.value)


async def test_a_network_error_is_retryable_and_leaks_nothing() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout talking to https://api.resend.com", request=request)

    with pytest.raises(MailError) as err:
        await mailer(boom).send(magic_link_message("a@example.test", URL, 30))
    assert not err.value.permanent


# ---------- the retry policy of the job ----------
def _decision(exception: Exception, attempts: int) -> object:
    from types import SimpleNamespace  # noqa: PLC0415

    from rm_worker.tasks.email import send_magic_link  # noqa: PLC0415

    strategy = send_magic_link.retry_strategy
    return strategy.get_retry_decision(exception=exception, job=SimpleNamespace(attempts=attempts))  # type: ignore[union-attr, arg-type]


def test_a_permanent_mail_error_is_never_retried() -> None:
    assert _decision(PermanentMailError("bad key"), 1) is None
    assert _decision(PermanentMailError("bad key"), 3) is None


def test_a_transient_mail_error_is_retried_with_waits_that_fit_a_30_minute_link() -> None:
    waits = []
    for attempt in (1, 2, 3):
        started = datetime.now(UTC)
        decision = _decision(TransientMailError("503"), attempt)
        assert decision is not None
        waits.append((decision.retry_at - started).total_seconds())  # type: ignore[attr-defined]
    assert waits == pytest.approx([9, 27, 81], abs=2)
    assert sum(waits) < 30 * 60  # the last retry still happens inside the link's lifetime


def test_the_job_gives_up_after_four_attempts() -> None:
    assert _decision(TransientMailError("503"), 4) is None


def test_an_unexpected_exception_is_not_retried() -> None:
    assert _decision(RuntimeError("bug"), 1) is None
