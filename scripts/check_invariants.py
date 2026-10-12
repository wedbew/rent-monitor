"""Fail unless every required invariant test ran and passed (the same check the CI `invariants` job performs).

Usage: python3 scripts/check_invariants.py invariants.xml
`tests/tooling/test_ci_local.py` keeps REQUIRED identical to the set in `.github/workflows/ci.yml`.
"""

import sys

from defusedxml import ElementTree as ET  # hardened parser (semgrep: use-defused-xml-parse)

REQUIRED = frozenset(
    {
        "test_invariant_rent_is_not_a_deal",
        "test_invariant_asking_is_not_deed",
        "test_invariant_admin_fee_is_opex",
        "test_invariant_deterministic_math",
        "test_invariant_fractional_ownership_rejected",
        "test_invariant_json_is_canonical_markdown_is_a_view",
        "test_invariant_llm_adjustment_is_clamped",
    }
)


def missing(junit_path: str) -> list[str]:
    root = ET.parse(junit_path).getroot()
    if root is None:
        raise SystemExit("empty junit file")
    cases = root.iter("testcase")
    passed = {c.get("name", "").split("[")[0] for c in cases if not list(c)}
    return sorted(REQUIRED - passed)


if __name__ == "__main__":
    gone = missing(sys.argv[1])
    if gone:
        raise SystemExit(f"invariant tests missing or not passing: {gone}")
    print("invariants: all required tests present and passing")
