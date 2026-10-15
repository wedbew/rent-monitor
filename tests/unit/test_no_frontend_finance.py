"""Invariant 4 at the file level: the SPA never implements finance (agents.md section 0, blueprint P0.3).

Display formatting is allowed; IRR, yield, tax, CAPEX, Max Bid and credit settlement are computed in
Python only. A name-based guard cannot prove the absence of arithmetic, so review and the ESLint money rules
(#268) carry the rest; this test stops the obvious regressions (the POC's `cashflow.ts` and
`appreciation.ts` reappearing).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNED_STEMS = {"cashflow", "appreciation", "irr", "moic", "cagr", "maxbid", "max_bid", "capex", "taxcalc"}
SKIP = {"node_modules", "dist"}


def test_no_finance_modules_exist_in_the_frontend() -> None:
    frontend = ROOT / "frontend"
    if not frontend.exists():
        return
    found = [
        str(p.relative_to(ROOT))
        for p in frontend.rglob("*")
        if p.is_file() and not SKIP & set(p.parts) and p.stem.split(".")[0].lower() in BANNED_STEMS
    ]
    assert found == []
