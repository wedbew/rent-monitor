"""Feature-flag resolution order (blueprint §3): override, then plan gate, then rollout bucket, then
default."""

from datetime import UTC, datetime, timedelta

import pytest
from rm_core.db.models import FeatureFlag, FeatureOverride
from rm_core.flags import decide, rollout_bucket

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def flag(
    *, default: bool = False, min_plan: str | None = None, rollout: int = 0, key: str = "screener"
) -> FeatureFlag:
    return FeatureFlag(
        key=key, description="d", enabled_default=default, min_plan=min_plan, rollout_pct=rollout
    )


def override(enabled: bool, expires: datetime | None = None) -> FeatureOverride:
    return FeatureOverride(
        flag_key="screener", user_id="u", enabled=enabled, reason="r", created_by="admin", expires_at=expires
    )


def test_an_unknown_flag_is_off() -> None:
    assert decide(None, None, user_id="u", plan="pro", now=NOW) is False


def test_the_default_decides_when_nothing_else_applies() -> None:
    assert decide(flag(default=True), None, user_id="u", plan="free", now=NOW) is True
    assert decide(flag(default=False), None, user_id="u", plan="free", now=NOW) is False


def test_an_override_beats_everything_below_it() -> None:
    gated = flag(default=False, min_plan="pro", rollout=0)
    assert (
        decide(gated, override(True), user_id="u", plan="free", now=NOW) is True
    )  # even below the plan gate
    on = flag(default=True, rollout=100)
    assert decide(on, override(False), user_id="u", plan="pro", now=NOW) is False


def test_expired_overrides_are_ignored() -> None:
    f = flag(default=True)
    assert decide(f, override(False, NOW - timedelta(seconds=1)), user_id="u", plan="free", now=NOW) is True
    assert decide(f, override(False, NOW + timedelta(seconds=1)), user_id="u", plan="free", now=NOW) is False
    assert (
        decide(f, override(False, NOW), user_id="u", plan="free", now=NOW) is True
    )  # exactly now is expired


def test_the_plan_gate_turns_a_flag_off_even_if_it_is_on_by_default_or_rolled_out() -> None:
    f = flag(default=True, min_plan="pro", rollout=100)
    assert decide(f, None, user_id="u", plan="free", now=NOW) is False
    assert decide(f, None, user_id="u", plan="pro", now=NOW) is True


def test_rollout_turns_a_flag_on_for_a_stable_share_of_users() -> None:
    f = flag(default=False, rollout=30)
    on = [u for u in (f"user-{i}" for i in range(2_000)) if decide(f, None, user_id=u, plan="free", now=NOW)]
    assert 0.25 < len(on) / 2_000 < 0.35  # about 30 %
    assert all(decide(f, None, user_id=u, plan="free", now=NOW) for u in on)  # stable: same answer every time


def test_rollout_edges_and_default_fallthrough() -> None:
    users = [f"u{i}" for i in range(300)]
    assert all(decide(flag(rollout=100), None, user_id=u, plan="free", now=NOW) for u in users)
    assert not any(decide(flag(rollout=0), None, user_id=u, plan="free", now=NOW) for u in users)
    assert all(
        decide(flag(default=True, rollout=1), None, user_id=u, plan="free", now=NOW) for u in users
    )  # default still applies


def test_buckets_are_stable_in_range_and_differ_per_flag() -> None:
    assert rollout_bucket("u", "a") == rollout_bucket("u", "a")
    assert 0 <= rollout_bucket("u", "a") < 100
    assert any(rollout_bucket(f"u{i}", "a") != rollout_bucket(f"u{i}", "b") for i in range(50))


@pytest.mark.parametrize("plan", ["free", "pro"])
def test_a_flag_without_a_plan_gate_ignores_the_plan(plan: str) -> None:
    assert decide(flag(default=True), None, user_id="u", plan=plan, now=NOW) is True  # type: ignore[arg-type]
