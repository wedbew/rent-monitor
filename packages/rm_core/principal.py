"""The authenticated caller. Every tenant-owned query takes one (agents.md §4); foreign resources are 404."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    """GDPR[personal-data]: email. Lives only in process memory (30 s cache) and is never logged."""

    user_id: str
    email: str
    role: str
    email_verified: bool
    session_id: int
    token_hash: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
