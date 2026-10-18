"""Otodom rental corpus contracts and repository semantics (RM-377, OTO-01).

Model tests live here; the repository contract is `tests/market_corpus_contract.py`, run against the
in-memory reference here and against Postgres in `tests/integration/test_market_corpus_pg.py` (RM-385).
Offline: no network, no database.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from market_corpus_contract import T0, ContractSuite, NewRepo, catalogue, entry, obs, run
from market_corpus_fake import InMemoryCorpus
from pydantic import ValidationError
from rm_contracts.market import (
    EXPECTED_CATALOGUE_SIZE,
    AgeBasis,
    DataStatus,
    InvalidRunTransitionError,
    LocationCatalogue,
    LocationCheckpoint,
    LocationEntry,
    OfferObservation,
    RentalOffer,
    RunState,
    check_transition,
    offer_from_observation,
)

# --- contract models -------------------------------------------------------------------------------


def test_models_reject_extra_fields_and_naive_times() -> None:
    with pytest.raises(ValidationError):
        LocationEntry.model_validate({**entry(1).model_dump(), "seller": "x"})
    with pytest.raises(ValidationError):
        OfferObservation(source_offer_id="1", location_id="loc-0", observed_at=datetime(2026, 1, 1))  # noqa: DTZ001


def test_catalogue_checksum_stable_and_validated() -> None:
    a, b = catalogue(3), LocationCatalogue.build(1, "x", [entry(2), entry(0), entry(1)])
    assert a.checksum == b.checksum  # order independent
    with pytest.raises(ValidationError):
        LocationCatalogue(version=1, source_ref="x", locations=a.locations, checksum="0" * 64)
    with pytest.raises(ValidationError):
        LocationCatalogue.build(1, "x", [entry(1), entry(1)])  # duplicate id
    assert not a.complete
    assert EXPECTED_CATALOGUE_SIZE == 727


def test_catalogue_round_trip() -> None:
    c = catalogue(4)
    assert LocationCatalogue.model_validate_json(c.model_dump_json()) == c


@pytest.mark.parametrize("path", ["", "Warszawa", "a//b", "a/b/c/d/e", "../x"])
def test_location_path_validated(path: str) -> None:
    with pytest.raises(ValidationError):
        LocationEntry(location_id="x", name="n", otodom_path=path)


def test_offer_money_is_decimal_and_positive() -> None:
    with pytest.raises(ValidationError):
        obs("1", rent="0")
    assert isinstance(obs("1").asking_rent_pln, Decimal)


def test_offer_age_publication_basis() -> None:
    pub = T0 - timedelta(days=10)
    o = offer_from_observation(obs("1", published_at=pub), "r", T0)
    assert o.age_basis is AgeBasis.publication
    assert o.expires_at == pub + timedelta(days=90)
    assert not o.archived(o.expires_at - timedelta(seconds=1))
    assert o.archived(o.expires_at)  # exactly at expiry: out of the cohort


def test_old_bootstrap_offer_enters_already_archived() -> None:
    o = offer_from_observation(obs("1", published_at=T0 - timedelta(days=120)), "r", T0)
    assert o.archived(T0)


def test_offer_age_fallback_missing_and_future_publication() -> None:
    missing = offer_from_observation(obs("1"), "r", T0)
    assert missing.age_basis is AgeBasis.first_seen
    assert not missing.source_date_issue
    future = offer_from_observation(obs("2", published_at=T0 + timedelta(days=2)), "r", T0)
    assert future.age_basis is AgeBasis.first_seen
    assert future.source_date_issue
    assert future.published_at is None
    assert future.expires_at == T0 + timedelta(days=90)


def test_offer_expiry_must_match_age_anchor() -> None:
    good = offer_from_observation(obs("1"), "r", T0)
    with pytest.raises(ValidationError):
        RentalOffer.model_validate({**good.model_dump(), "expires_at": T0 + timedelta(days=30)})
    with pytest.raises(ValidationError):
        RentalOffer.model_validate({**good.model_dump(), "price_basis": "deed"})  # invariant 2


def test_unpriced_offer_keeps_identity() -> None:
    o = offer_from_observation(obs("1", rent=None), "r", T0)
    assert not o.priced
    assert o.source_offer_id == "1"


def test_run_state_machine() -> None:
    r = run("r1")
    assert not r.coverage_complete
    with pytest.raises(InvalidRunTransitionError):
        check_transition(RunState.published, RunState.running)
    zero = r.model_copy(update={"pages_expected": 1, "pages_fetched": 1})
    assert zero.coverage_complete  # valid empty search is complete
    assert not zero.model_copy(update={"truncated": True}).coverage_complete


def test_checkpoint_data_status() -> None:
    assert LocationCheckpoint(location_id="x").data_status(T0) is DataStatus.unavailable
    cp = LocationCheckpoint(location_id="x", bootstrap_completed_at=T0, last_successful_refresh_at=T0)
    assert cp.data_status(T0 + timedelta(hours=36)) is DataStatus.fresh
    assert cp.data_status(T0 + timedelta(hours=37)) is DataStatus.delayed
    assert cp.data_status(T0 + timedelta(hours=73)) is DataStatus.stale
    gap = cp.model_copy(update={"unresolved_gap_since": T0})
    assert gap.data_status(T0) is DataStatus.stale


@pytest.fixture
def new_repo() -> NewRepo:
    return InMemoryCorpus


class TestInMemoryCorpus(ContractSuite):
    """The shared repository contract against the in-memory reference."""
