"""Run the engine in a killable child process with a memory cap (blueprint §4.5 b, #186).

The engine is synchronous CPU work. In the worker's event loop a call that never returns cannot be cancelled
and would hold the audit slot (and the user's reserved credit) forever, so it runs in a child process:

* the parent sends the typed inputs as JSON lines on stdin and reads the `DealAnalysis` JSON from stdout;
* the child lives in its own process group and is SIGKILLed with that group on timeout, on cancellation
  (deploy restart, worker shutdown) and on any error path, so no orphan outlives its audit;
* the child lowers `RLIMIT_AS` at start, so a runaway allocation ends the child (not the worker or its
  neighbours);
* the child's output is size-capped and strictly parsed; a domain error (fractional ownership) is re-raised as
  the same typed error, anything else becomes `EngineChildError`.

Money stays `Decimal` end to end: the models serialise to JSON strings and are validated on the way back.
"""

import asyncio
import contextlib
import importlib
import json
import os
import signal
import sys
from decimal import Decimal
from typing import Any, Protocol

import structlog
from deal_analyzer import DealAnalysis, FractionalOwnershipError, Listing, RentInput, VisionOutput

log = structlog.get_logger(__name__)
DEFAULT_TARGET = "deal_analyzer:analyse_listing"
MAX_OUTPUT_BYTES = 5 * 1024 * 1024  # a DealAnalysis is a few tens of KB; anything bigger is a bug
MAX_STDERR_BYTES = 8 * 1024
EXIT_DOMAIN_ERROR = 3


class EngineChildError(RuntimeError):
    """The engine child died, was killed, exceeded its memory cap or returned garbage."""


class EngineRunner(Protocol):
    async def run(
        self,
        listing: Listing,
        *,
        rent: RentInput,
        risk_free: Decimal,
        timeout_s: float,
        vision: VisionOutput | None = None,
        model: str = "none",
        prompt_version: str = "none",
    ) -> DealAnalysis: ...


class ChildEngine:
    """Production runner. `target` is `module:function`, a trusted constructor argument (never user input)."""

    def __init__(self, *, memory_mb: int = 1024, target: str = DEFAULT_TARGET) -> None:
        self._memory_bytes = memory_mb * 1024 * 1024
        self._target = target

    async def run(
        self,
        listing: Listing,
        *,
        rent: RentInput,
        risk_free: Decimal,
        timeout_s: float,
        vision: VisionOutput | None = None,
        model: str = "none",
        prompt_version: str = "none",
    ) -> DealAnalysis:
        # Single-line documents (compact JSON has no raw newline): strict models parse JSON, not dicts.
        # Optional fourth and fifth lines carry the parsed vision answer; the engine clamps it (invariant 4).
        lines = [listing.model_dump_json().encode(), rent.model_dump_json().encode(), str(risk_free).encode()]
        if vision is not None:
            meta = json.dumps({"model": model, "prompt_version": prompt_version})
            lines += [vision.model_dump_json().encode(), meta.encode()]
        request = b"\n".join(lines)
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "rm_worker.engine_child",
            self._target,
            str(self._memory_bytes),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # own process group: the kill below reaches anything the child spawned
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(request), timeout=max(timeout_s, 0.001))
        except (
            BaseException
        ):  # timeout, cancellation (shutdown) or a broken pipe: never leave the child behind
            await _kill(proc)
            raise
        if proc.returncode == EXIT_DOMAIN_ERROR:
            _raise_domain_error(out)
        if proc.returncode != 0:
            log.error(
                "engine_child.failed",
                returncode=proc.returncode,
                stderr=err[-MAX_STDERR_BYTES:].decode(errors="replace"),
            )
            msg = f"engine child exited with {proc.returncode}"
            raise EngineChildError(msg)
        if len(out) > MAX_OUTPUT_BYTES:
            msg = "engine child output exceeds the size cap"
            raise EngineChildError(msg)
        try:
            return DealAnalysis.model_validate_json(out)
        except ValueError as exc:
            msg = "engine child returned an invalid DealAnalysis"
            raise EngineChildError(msg) from exc


async def _kill(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
    with contextlib.suppress(Exception):
        await asyncio.shield(proc.wait())


def _raise_domain_error(out: bytes) -> None:
    """Only invariant 5 is a domain error; anything else the child reports is an engine failure."""
    try:
        error = json.loads(out)
        if error["error"] != "FractionalOwnershipError":
            raise KeyError(error["error"])
        otodom_id = str(error["otodom_id"])[:40]
        evidence = tuple(str(e)[:200] for e in error["evidence"][:10])
    except (ValueError, KeyError, TypeError) as exc:
        msg = "engine child reported an unknown domain error"
        raise EngineChildError(msg) from exc
    raise FractionalOwnershipError(otodom_id, evidence)


# --------------------------------------------------------------------------------------- child side
def _limit_memory(memory_bytes: int) -> None:
    """Best effort: `RLIMIT_AS` is enforced on Linux (the production host); macOS ignores or rejects it."""
    try:
        import resource  # noqa: PLC0415  (POSIX only, and only the child needs it)

        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except (ImportError, ValueError, OSError):
        sys.stderr.write("engine_child: no memory cap applied on this platform\n")


def _resolve(target: str) -> Any:
    module, _, name = target.partition(":")
    return getattr(importlib.import_module(module), name)


def _main(argv: list[str]) -> int:
    target, memory_bytes = argv[1], int(argv[2])
    result, sys.stdout = (
        sys.stdout,
        sys.stderr,
    )  # stdout is the result channel: stray prints must not corrupt it
    _limit_memory(memory_bytes)
    function = _resolve(target)
    listing_json, rent_json, risk_free, *extra = sys.stdin.buffer.read().split(b"\n")
    listing = Listing.model_validate_json(listing_json)
    rent = RentInput.model_validate_json(rent_json)
    options: dict[str, Any] = {}
    if extra:
        vision_json, meta_json = extra
        meta = json.loads(meta_json)
        options = {
            "vision": VisionOutput.model_validate_json(vision_json),
            "model": str(meta["model"])[:120],
            "prompt_version": str(meta["prompt_version"])[:40],
        }
    try:
        analysis = function(listing, rent=rent, risk_free=Decimal(risk_free.decode()), **options)
    except FractionalOwnershipError as exc:
        result.write(
            json.dumps(
                {"error": "FractionalOwnershipError", "otodom_id": exc.otodom_id, "evidence": exc.evidence}
            )
        )
        return EXIT_DOMAIN_ERROR
    result.write(analysis.model_dump_json())
    return 0


if __name__ == "__main__":  # pragma: no cover  (exercised through ChildEngine in a subprocess)
    sys.exit(_main(sys.argv))
