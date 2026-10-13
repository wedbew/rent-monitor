"""`/api/audits` schemas: strict inbound models, and enums that cannot drift from the database enums."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from rm_contracts.audits import MAX_LISTING_REF, AuditCreate, AuditOut, AuditState, ChargeStateName
from rm_contracts.jobs import AUDIT_QUEUE, RUN_AUDIT_TASK
from rm_core.db.models import AuditStatus, ChargeState


def test_state_enums_mirror_the_database_enums() -> None:
    assert {s.value for s in AuditState} == {s.value for s in AuditStatus}
    assert {s.value for s in ChargeStateName} == {s.value for s in ChargeState}


def test_job_names_match_the_worker_task() -> None:
    from rm_worker.tasks.audit import run_audit  # noqa: PLC0415

    assert run_audit.name == RUN_AUDIT_TASK
    assert run_audit.queue == AUDIT_QUEUE


def test_create_rejects_unknown_fields_and_bad_sizes() -> None:
    assert AuditCreate(listing_ref="  ID4CpHB  ").listing_ref == "ID4CpHB"
    with pytest.raises(ValidationError):
        AuditCreate.model_validate({"listing_ref": "ID4CpHB", "surprise": 1})
    with pytest.raises(ValidationError):
        AuditCreate(listing_ref="x" * (MAX_LISTING_REF + 1))
    with pytest.raises(ValidationError):
        AuditCreate(listing_ref="   ")
    with pytest.raises(ValidationError):
        AuditCreate.model_validate({"listing_ref": "ID4CpHB", "lang": "de"})


def test_money_is_decimal_and_serialises_as_a_string() -> None:
    now = "2026-10-13T10:00:00Z"
    out = AuditOut.model_validate(
        {
            "audit_id": uuid4(),
            "otodom_id": "ID4CpHB",
            "status": "succeeded",
            "error_code": None,
            "charge_state": "captured",
            "created_at": now,
            "started_at": now,
            "finished_at": now,
            "grade": "B",
            "asking_price_pln": "450000.00",
            "max_bid_pln": "431250.50",
            "irr_10y": "0.0712",
            "capex_pln": "21000.00",
            "result": {"schema_version": 1},
        }
    )
    assert isinstance(out.max_bid_pln, Decimal)
    dumped = out.model_dump(mode="json")
    assert dumped["max_bid_pln"] == "431250.50"
    assert dumped["asking_price_pln"] == "450000.00"
