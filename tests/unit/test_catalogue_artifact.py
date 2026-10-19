"""The committed Otodom catalogue artifact is internally consistent and honest about the 727 (RM-411).

LEGAL[third-party-data]: reads location paths and names only (RM-411).
"""

import json
from pathlib import Path

import pytest
from rm_worker.importers.otodom_catalogue import ArtifactError, catalogue_from_artifact

ARTIFACT = Path(__file__).parents[2] / "docs" / "market" / "otodom-catalogue-v1.json"


def data() -> dict:
    return json.loads(ARTIFACT.read_text())


def test_the_committed_catalogue_verifies_and_matches_its_own_account() -> None:
    d = data()
    catalogue = catalogue_from_artifact(d)
    assert len(catalogue.locations) == d["reconciliation"]["discovered"] == len(d["locations"])
    assert catalogue.checksum == d["checksum"]
    assert d["reconciliation"]["approved_target"] == 727
    assert d["reconciliation"]["difference_from_target"] == len(catalogue.locations) - 727
    assert d["reconciliation"]["identity_match_possible"] is False  # never claims to be the owner's list
    assert len(d["sitemap"]["sha256"]) == 64  # provenance: which sitemap this came from
    assert d["source_ref"].startswith("otodom-sitemap:")


def test_every_place_was_probed_and_none_is_nested_in_another() -> None:
    d = data()
    assert all(loc["probe"]["status"] == "ok" for loc in d["locations"])
    assert all(isinstance(loc["probe"]["total_items"], int) for loc in d["locations"])
    paths = [loc["otodom_path"] for loc in d["locations"]]
    assert len(paths) == len(set(paths))
    assert all(1 <= p.count("/") + 1 <= 4 for p in paths)  # gmina-level: depth 3 or 4 below the voivodeship


def test_a_tampered_or_nested_artifact_is_refused() -> None:
    d = data()
    d["locations"][0]["name"] = d["locations"][0]["name"]  # a name is display data: allowed to differ
    catalogue_from_artifact(d)
    d["locations"][0]["otodom_path"] = "changed/path/here"
    with pytest.raises(ArtifactError, match="checksum"):
        catalogue_from_artifact(d)
    d = data()
    first = next(loc for loc in d["locations"] if loc["otodom_path"].count("/") == 2)  # a gmina
    d["locations"].append(
        {**first, "location_id": "child-aaaaaaaa", "otodom_path": first["otodom_path"] + "/child"}
    )
    from rm_contracts.market import LocationEntry, catalogue_checksum  # noqa: PLC0415

    d["checksum"] = catalogue_checksum(
        [
            LocationEntry(location_id=r["location_id"], name=r["name"], otodom_path=r["otodom_path"])
            for r in d["locations"]
        ]
    )
    with pytest.raises(ArtifactError, match="nested"):
        catalogue_from_artifact(d)
