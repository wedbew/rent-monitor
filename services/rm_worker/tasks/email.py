"""Transactional email jobs (queue `ops`). The API defers them by name, so it never imports the worker.

GDPR[processor]: the job arguments carry the recipient address and, for the magic link, the single-use token
inside the URL, and Resend receives the message (RM-12). The token is valid for 30 minutes and once; the
plaintext sits in `procrastinate_jobs` until the job is removed (docs/LIMITATIONS.md L-011).
"""

import hashlib
from html import escape

import httpx
import structlog
from procrastinate import RetryStrategy
from rm_contracts.jobs import OPS_QUEUE, SEND_AUTH_MAIL_TASK, SEND_MAGIC_LINK_TASK
from rm_core.settings import Settings, get_settings

from rm_worker.app import app
from rm_worker.clients.resend import (
    LogMailer,
    Mailer,
    Message,
    PermanentMailError,
    ResendMailer,
    TransientMailError,
    is_onboarding_sender,
)

log = structlog.get_logger(__name__)


def magic_link_message(email: str, url: str, ttl_minutes: int) -> Message:
    """Polish transactional mail; plain text and minimal HTML, no tracking pixels, one link."""
    subject = "Twój link do logowania w RentMonitor"
    text = (
        f"Kliknij, aby zalogować się do RentMonitor:\n\n{url}\n\n"
        f"Link działa jednorazowo przez {ttl_minutes} minut. Jeśli to nie Ty, zignoruj tę wiadomość.\n"
    )
    html = (
        "<p>Kliknij, aby zalogować się do RentMonitor:</p>"
        f'<p><a href="{escape(url, quote=True)}">Zaloguj się</a></p>'
        f"<p>Link działa jednorazowo przez {ttl_minutes} minut. Jeśli to nie Ty, zignoruj tę wiadomość.</p>"
    )
    key = hashlib.sha256(f"magic:{email}:{url}".encode()).hexdigest()  # a retried job never sends twice
    return Message(to=email, subject=subject, text=text, html=html, idempotency_key=key)


def build_mailer(settings: Settings, http: httpx.AsyncClient) -> Mailer:
    key = settings.resend_api_key.get_secret_value()
    if key:
        if settings.app_env == "production" and is_onboarding_sender(settings.mail_from):
            raise PermanentMailError("MAIL_FROM is the Resend onboarding sender; verify a domain first")
        return ResendMailer(http, key, settings.mail_from)
    if settings.app_env == "production":
        raise PermanentMailError("RESEND_API_KEY is not set")
    return LogMailer()


async def deliver_magic_link(mailer: Mailer, settings: Settings, email: str, url: str) -> None:
    await mailer.send(magic_link_message(email, url, settings.magic_link_ttl_minutes))
    if settings.app_env == "development" and isinstance(mailer, LogMailer):
        # Development convenience only (blueprint §4.6 manual auth check); production never reaches this line.
        log.info("magic_link_dev", url=url)


@app.task(
    queue=OPS_QUEUE,
    name=SEND_MAGIC_LINK_TASK,
    # Waits of 9, 27 and 81 s: the link is valid for 30 minutes, so a late retry would send a dead link.
    # Only transient failures retry; a bad key or sender fails at once instead of keeping the token around.
    retry=RetryStrategy(max_attempts=4, exponential_wait=3, retry_exceptions=[TransientMailError]),
)
async def send_magic_link(email: str, url: str) -> None:
    settings = get_settings()
    async with httpx.AsyncClient() as http:
        mailer = build_mailer(settings, http)
        await deliver_magic_link(mailer, settings, email, url)
    log.info("magic_link_sent")


def auth_message(kind: str, email: str, url: str | None, settings: Settings) -> Message:
    """Password-auth mail (ADR 0013): Polish, plain text plus minimal HTML, at most one link."""
    if kind == "register" and url:
        hours = settings.register_token_ttl_hours
        subject = "Potwierdź rejestrację w RentMonitor"
        text = (
            f"Kliknij, aby potwierdzić adres e-mail i założyć konto w RentMonitor:\n\n{url}\n\n"
            f"Link działa jednorazowo przez {hours} godz. Jeśli to nie Ty, zignoruj tę wiadomość.\n"
        )
        html = (
            "<p>Kliknij, aby potwierdzić adres e-mail i założyć konto w RentMonitor:</p>"
            f'<p><a href="{escape(url, quote=True)}">Potwierdź rejestrację</a></p>'
            f"<p>Link działa jednorazowo przez {hours} godz. Jeśli to nie Ty, zignoruj tę wiadomość.</p>"
        )
        key = hashlib.sha256(f"register:{email}:{url}".encode()).hexdigest()
    elif kind == "account_exists":
        subject = "Masz już konto w RentMonitor"
        text = (
            "Ktoś próbował założyć konto w RentMonitor na ten adres, ale konto już istnieje.\n"
            "Zaloguj się albo użyj opcji „Nie pamiętam hasła”. Jeśli to nie Ty, zignoruj tę wiadomość.\n"
        )
        html = "".join(f"<p>{escape(line)}</p>" for line in text.strip().split("\n"))
        key = hashlib.sha256(f"exists:{email}".encode()).hexdigest()
    else:
        raise PermanentMailError(f"unknown auth mail kind {kind!r}")
    return Message(to=email, subject=subject, text=text, html=html, idempotency_key=key)


@app.task(
    queue=OPS_QUEUE,
    name=SEND_AUTH_MAIL_TASK,
    retry=RetryStrategy(max_attempts=4, exponential_wait=3, retry_exceptions=[TransientMailError]),
)
async def send_auth_mail(kind: str, email: str, url: str | None = None) -> None:
    """GDPR[processor]: Resend receives the address and, for `register`, the single-use link. The token is
    hashed in the database and its plaintext lives only in this job's arguments until the job is removed
    (docs/LIMITATIONS.md L-011)."""
    settings = get_settings()
    async with httpx.AsyncClient() as http:
        mailer = build_mailer(settings, http)
        await mailer.send(auth_message(kind, email, url, settings))
        if settings.app_env == "development" and isinstance(mailer, LogMailer) and url:
            log.info("auth_mail_dev", kind=kind, url=url)  # development only; production never logs a link
    log.info("auth_mail_sent", kind=kind)
