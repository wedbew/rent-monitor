"""Resend email client behind a small protocol, with an offline fake for tests (agents.md §3).

GDPR[processor]: Resend receives the recipient address and the message body (RM-12). Never log the address
or the link.
Failures raise `MailError`; the Procrastinate task retries with backoff. Live delivery is untested until the
owner's
Resend key and sending domain are verified (docs/BLOCKERS.md B-004).
"""

from dataclasses import dataclass, field
from typing import Protocol

import httpx
import structlog

log = structlog.get_logger(__name__)
RESEND_URL = "https://api.resend.com/emails"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
ONBOARDING_DOMAIN = "resend.dev"


class MailError(Exception):
    """The provider refused or could not be reached; safe to retry unless `permanent`."""

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str
    idempotency_key: str


class Mailer(Protocol):
    async def send(self, message: Message) -> None: ...


@dataclass
class ResendMailer:
    http: httpx.AsyncClient
    api_key: str = field(repr=False)  # never in a traceback, log line or test failure
    mail_from: str

    async def send(self, message: Message) -> None:
        try:
            response = await self.http.post(
                RESEND_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": message.idempotency_key,
                },
                json={
                    "from": self.mail_from,
                    "to": [message.to],
                    "subject": message.subject,
                    "text": message.text,
                    "html": message.html,
                },
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise MailError(f"resend unreachable: {type(exc).__name__}") from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise MailError(f"resend answered HTTP {response.status_code}")
        if response.status_code >= 400:  # bad key, unverified domain, invalid address: retrying will not help
            raise MailError(f"resend refused with HTTP {response.status_code}", permanent=True)


@dataclass
class LogMailer:
    """Development only: logs that a mail would be sent. The link itself is logged by the task, never here."""

    sent: list[Message] = field(default_factory=lambda: [])

    async def send(self, message: Message) -> None:
        self.sent.append(message)
        log.info("mail_not_sent_dev", subject=message.subject)


def is_onboarding_sender(mail_from: str) -> bool:
    return mail_from.strip().lower().rstrip(">").endswith(f"@{ONBOARDING_DOMAIN}")
