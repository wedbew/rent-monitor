"""Transactional email jobs (queue `ops`). The API defers them by name, so it never imports the worker.

GDPR[processor]: the job arguments carry the recipient address and, for the magic link, the single-use token
inside
the URL, and Resend receives the message (RM-12). The token is valid for 30 minutes and once; the plaintext
sits in
`procrastinate_jobs` until the job is removed (docs/LIMITATIONS.md L-011).
"""

import hashlib
from html import escape

import httpx
import structlog
from procrastinate import RetryStrategy
from rm_contracts.jobs import OPS_QUEUE, SEND_MAGIC_LINK_TASK
from rm_core.settings import Settings, get_settings

from rm_worker.app import app
from rm_worker.clients.resend import LogMailer, Mailer, MailError, Message, ResendMailer, is_onboarding_sender

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
            raise MailError(
                "MAIL_FROM is the Resend onboarding sender; verify a domain first", permanent=True
            )
        return ResendMailer(http, key, settings.mail_from)
    if settings.app_env == "production":
        raise MailError("RESEND_API_KEY is not set", permanent=True)
    return LogMailer()


async def deliver_magic_link(mailer: Mailer, settings: Settings, email: str, url: str) -> None:
    await mailer.send(magic_link_message(email, url, settings.magic_link_ttl_minutes))
    if settings.app_env == "development" and isinstance(mailer, LogMailer):
        # Development convenience only (blueprint §4.6 manual auth check); production never reaches this line.
        log.info("magic_link_dev", url=url)


@app.task(
    queue=OPS_QUEUE,
    name=SEND_MAGIC_LINK_TASK,
    retry=RetryStrategy(max_attempts=4, exponential_wait=10),
)
async def send_magic_link(email: str, url: str) -> None:
    settings = get_settings()
    async with httpx.AsyncClient() as http:
        mailer = build_mailer(settings, http)
        await deliver_magic_link(mailer, settings, email, url)
    log.info("magic_link_sent")
