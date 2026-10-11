# Engine specification (DRAFT for owner approval)

**Status:** draft proposal, **not approved**. Written by an agent from the blueprint and general market practice, not from POC
code. Every value is a *recommended default* the owner may change. Items marked **(accountant)** are tax facts to be confirmed
by an accountant before launch. Approve by editing the *Decision* column (or replying "approve all"); then `#17` unblocks
(B-007). Terms: *Asking price* = advertised price; *PLN* amounts are `Decimal`; the engine is pure Python (invariant 4).

## How to read this
The engine takes one parsed listing plus market context and returns a `DealAnalysis`: purchase cost, yearly cash flows for
a horizon, returns (yield, IRR, MOIC, CAGR), tax, CAPEX, **Max Bid** and a grade. The 13 questions come from `docs/ROADMAP.md` §8 (D-01).

| # | Question | Recommended default | Decision |
|---|---|---|---|
| 1 | Horizon, periods, start | **10 years**, annual periods, purchase at t=0, first rent from month 1 after a fit-out period equal to the CAPEX duration estimate (default 2 months). Also report 5-year view. | |
| 2 | Purchase costs | PCC **2%** of price on the secondary market (not on VAT sales, where VAT is in the price) **(accountant)**; notary fee by the statutory scale for the price (table in code, versioned); court fees: land-register entry 200 PLN (+200 PLN if mortgage) **(accountant)**; broker commission input, default **0%** (buyer usually pays none; user can enter 2.5% + VAT). Non-residential/VAT sale detected → no PCC, VAT shown separately. | |
| 3 | Operating costs | Admin fee (`czynsz`) = OPEX, never income (invariant 3). Property tax from a per-gmina residential rate table, default **0.50 PLN/m²/yr** if unknown. Insurance **0.15%** of price/yr. Vacancy **1 month/yr (8.3%)**. Management **0%** self-managed (option **8%** of rent). Maintenance reserve **1.0%** of price/yr. All sources recorded in the result. | |
| 4 | CAPEX | Catalog price per m² and per item (bathroom, kitchen, floors, windows, wiring), nominal PLN, with a **regional multiplier** by city tier (the POC audit found one national constant misprices big cities); condition scale from vision: *good / refresh / renovation / shell*. Unknown condition → *refresh* + lowered confidence. | |
| 5 | Rent | Anchor = median of rental listings in the same city and size bucket (from the market lane); hedonic adjustment for size/floor/standard. **Thin market** (< 10 comparables): widen the interval and lower confidence; (< 3): refuse a rent number and grade "N". Rent growth **3%/yr** nominal, inflation input **3%/yr** (nominal results by default, real view optional). | |
| 6 | Tax | Individual, rental via **ryczałt**: **8.5%** up to 100,000 PLN/yr of rent, **12.5%** above **(accountant)**; no cost deduction under ryczałt (so admin fee reduces cash, not tax). Option flag for tax scale 12/32% with costs, off by default. Sale: **19%** on gain if sold within 5 years from the end of the purchase year, else 0 **(accountant)**. | |
| 7 | Financing | **Cash purchase** by default (unlevered). Optional leverage block: LTV (default 0 / 70%), rate (default WIBOR-3M proxy + margin 2.0%), tenor 25 years, annuity, bank costs 1% . Leverage affects IRR only, never Max Bid. | |
| 8 | Exit | Exit value = price at purchase grown by the **deed**-based city appreciation rate (BDL, never asking data; invariant 2), default floor 0% / cap 5%; selling costs **2%** of exit value; exit-year tax per #6. Income-approach exit (rent / cap rate) shown separately, never blended. | |
| 9 | Discount / hurdle | Risk-free = Polish 10Y government bond yield (latest from a fresh macro source, N-12); hurdle = risk-free + **3.0%** premium. | |
| 10 | Max Bid | Highest price at which the **unlevered 10-year IRR after tax, with all purchase costs and CAPEX included, ≥ hurdle (#9)**. Found by monotone bisection on price (property-tested). Never above the asking price × 1.0 for the verdict "buy at asking". | |
| 11 | Grades | By IRR minus hurdle: **A** ≥ +3.0 pp, **B** ≥ +1.5, **C** ≥ 0, **D** ≥ −1.5, **E** below. **N** = insufficient data (thin market, missing area/price, fractional ownership shown as rejected, not graded). | |
| 12 | LLM role | The LLM may only classify photos (condition, renders/staging excluded), transcribe floor-plan text, and propose adjustments to the CAPEX estimate and to rent. Each adjustment is **clamped to ±15% of the deterministic base**, logged with model and prompt version, and the audit can be recomputed without the LLM (invariant 4). | |
| 13 | Rounding | Computation in `Decimal` (28 digits). Money rounded **half-up to 0.01 PLN** only for output; rates to 4 decimals; IRR solved to 1e-8. Same input must give a byte-identical `returns` block. | |

## Things the draft deliberately does NOT decide
- Free tier and Pro allowance (D-04), VAT presentation of the 100 PLN price (D-03).
- Which extras ship (analyst text audit, seller questions, redesign): D-07.
- Legal conclusions about scraping or images (B-012).

## After approval
1. Owner edits the *Decision* column or answers "approve all" in issue #43.
2. Agents split `#17` into N-01..N-11 (roadmap §9.2) and implement each section test-first with these numbers as the
   written contract; every default above becomes a named, versioned constant with a source note.
3. Tax rows stay flagged until an accountant confirms them (PRE-DEPLOYMENT §4).
