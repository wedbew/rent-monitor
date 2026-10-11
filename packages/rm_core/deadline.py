"""A monotonic deadline passed down every outbound call (blueprint §6 "One deadline per audit")."""

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Deadline:
    expires_at: float  # time.monotonic() value

    @classmethod
    def after(cls, seconds: float) -> "Deadline":
        return cls(time.monotonic() + seconds)

    def remaining(self) -> float:
        return max(0.0, self.expires_at - time.monotonic())

    @property
    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def cap(self, seconds: float) -> float:
        """A timeout no longer than what is left."""
        return min(seconds, self.remaining())
