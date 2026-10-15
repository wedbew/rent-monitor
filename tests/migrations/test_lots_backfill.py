"""Migration 0009 turns existing balances into explicit lots (docs/PADDLE-INTEGRATION.md section 4)."""

from uuid import uuid4

from pytest_alembic import MigrationContext
from sqlalchemy import Connection, Engine, text

AUDIT_SQL = (
    "INSERT INTO app.audit (user_id, otodom_id, status, charge_source, charge_state, analyst, engine_version,"
    " schema_version) VALUES (:u, :o, :st, 'credit', :cs, :an, 't', 1) RETURNING id"
)
LEDGER_SQL = (
    "INSERT INTO app.credit_ledger (user_id, delta, reason, idempotency_key, audit_id)"
    " VALUES (:u, :d, :r, :k, :a)"
)
LOT_SQL = (
    "SELECT user_id, source, granted, available, reserved, consumed, revoked, frozen"
    " FROM app.report_credit_lot"
)
ALLOCATION_SQL = (
    "SELECT a.units, a.state, l.user_id FROM app.report_credit_allocation a"
    " JOIN app.report_credit_lot l ON l.id = a.lot_id"
)
UNEXPLAINED_SQL = (
    "SELECT count(*) FROM app.report_credit_lot l"
    " WHERE l.available <> (SELECT balance FROM app.credit_account c WHERE c.user_id = l.user_id)"
)


def _user(conn: Connection, uid: str, balance: int) -> None:
    conn.execute(
        text("INSERT INTO app.app_user (id, email) VALUES (:i, :e)"), {"i": uid, "e": f"{uid}@x.test"}
    )
    conn.execute(
        text("INSERT INTO app.credit_account (user_id, balance) VALUES (:u, :b)"), {"u": uid, "b": balance}
    )


def _audit(conn: Connection, uid: str, oid: str, *, state: str, analyst: bool = False) -> str:
    conn.execute(
        text("INSERT INTO app.listing (otodom_id, url) VALUES (:o, 'https://x.test') ON CONFLICT DO NOTHING"),
        {"o": oid},
    )
    status = "queued" if state == "reserved" else "succeeded"
    params = {"u": uid, "o": oid, "st": status, "cs": state, "an": analyst}
    return str(conn.execute(text(AUDIT_SQL), params).scalar_one())


def _ledger(
    conn: Connection, uid: str, delta: int, reason: str, key: str, *, audit: str | None = None
) -> None:
    conn.execute(text(LEDGER_SQL), {"u": uid, "d": delta, "r": reason, "k": key, "a": audit})


def test_balances_reservations_consumption_and_removals_become_one_migration_lot_each(
    alembic_runner: MigrationContext, alembic_engine: Engine
) -> None:
    alembic_runner.migrate_up_before("0009")
    rich, analyst, idle = (str(uuid4()) for _ in range(3))
    with alembic_engine.begin() as conn:
        _user(conn, rich, 4)  # +5 signup, +2 admin, a captured audit, an in-flight audit, an operator removal
        _user(conn, analyst, 1)  # +3 signup, an in-flight analyst audit that costs 2
        _user(conn, idle, 0)
        _ledger(conn, rich, 5, "signup_grant", f"signup:{rich}")
        _ledger(conn, rich, 2, "admin_adjust", f"admin:{rich}:1")
        done = _audit(conn, rich, "IDMIG1", state="captured")
        _ledger(conn, rich, -1, "reserve", f"reserve:{done}", audit=done)
        flying = _audit(conn, rich, "IDMIG2", state="reserved")
        _ledger(conn, rich, -1, "reserve", f"reserve:{flying}", audit=flying)
        _ledger(conn, rich, -1, "admin_adjust", f"admin:{rich}:2")
        _ledger(conn, analyst, 3, "signup_grant", f"signup:{analyst}")
        held = _audit(conn, analyst, "IDMIG3", state="reserved", analyst=True)
        _ledger(conn, analyst, -2, "reserve", f"reserve:{held}", audit=held)

    alembic_runner.migrate_up_one()

    with alembic_engine.begin() as conn:
        lots = {row.user_id: row for row in conn.execute(text(LOT_SQL)).all()}
        assert idle not in lots  # an account that never held units gets no lot
        r = lots[rich]
        # granted 7 = the 5 + 2 ever granted = 4 available + 1 reserved + 1 consumed + 1 operator removal
        assert (r.source, r.granted, r.available, r.reserved, r.consumed, r.revoked, r.frozen) == (
            "migration",
            7,
            4,
            1,
            1,
            1,
            False,
        )
        n = lots[analyst]
        assert (n.granted, n.available, n.reserved, n.consumed, n.revoked) == (3, 1, 2, 0, 0)
        allocations = conn.execute(text(ALLOCATION_SQL)).all()
        assert sorted((x.user_id, x.units, x.state) for x in allocations) == sorted(
            [(rich, 1, "reserved"), (analyst, 2, "reserved")]
        )
        assert conn.execute(text(UNEXPLAINED_SQL)).scalar_one() == 0  # lots explain every cached balance

    alembic_runner.migrate_down_one()
    with alembic_engine.begin() as conn:  # 0009 only adds tables: the existing ones are untouched
        balance = conn.execute(text("SELECT balance FROM app.credit_account WHERE user_id = :u"), {"u": rich})
        assert balance.scalar_one() == 4
