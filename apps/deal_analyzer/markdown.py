"""Markdown view of a `DealAnalysis` (invariant 6: JSON is canonical, Markdown is a view).

The renderer takes only the analysis object (which round-trips through its JSON), computes nothing, and
prints numbers exactly as
the JSON holds them, with grouping separators added for readability. Every number it shows therefore
exists in the JSON.
"""

from decimal import Decimal
from typing import Literal

from deal_analyzer.analysis import DealAnalysis

Lang = Literal["pl", "en"]

_T: dict[Lang, dict[str, str]] = {
    "en": {
        "verdict": "Verdict",
        "grade": "Grade",
        "buy_at_asking": "Buy at asking",
        "negotiate": "Negotiate",
        "pass": "Pass",
        "insufficient_data": "Insufficient data",
        "price": "Asking price",
        "max_bid": "Max Bid",
        "max_bid_none": "no price reaches the hurdle",
        "hurdle": "Hurdle (target IRR)",
        "irr": "IRR (10 years, unlevered, after tax)",
        "moic": "MOIC",
        "cagr": "CAGR",
        "gross_yield": "Gross yield",
        "net_yield": "Net yield",
        "sens_minus": "Max Bid if appreciation is 1 pp lower",
        "sens_plus": "Max Bid if appreciation is 1 pp higher",
        "purchase": "Purchase costs",
        "pcc": "PCC tax",
        "notary": "Notary (with VAT)",
        "copies": "Deed copies",
        "court": "Court fees",
        "broker": "Broker",
        "capex": "CAPEX",
        "invested": "Total invested",
        "years": "Cash flow by year",
        "year": "Year",
        "rent": "Rent",
        "costs": "Costs",
        "tax": "Income tax",
        "net": "Net cash flow",
        "exit": "Exit",
        "exit_value": "Exit value",
        "selling": "Selling costs",
        "sale_tax": "Sale tax",
        "proceeds": "Net proceeds",
        "rent_basis": "Rent basis",
        "asking": "asking-based (comparables are asking rents; haircut applied)",
        "achieved": "achieved rents",
        "notes": "Notes and limits",
        "confidence": "Confidence",
        "not_computed": "not computed",
        "w_capex_prices_are_placeholders": (
            "CAPEX prices are placeholders, not market data: do not rely on this valuation."
        ),
        "w_rent_refused_too_few_comparables": "Too few comparable rents: no grade is given.",
        "w_rent_thin_market": "Thin rental market: the rent is uncertain.",
        "w_vision_unavailable": "Photos were not analysed: condition and CAPEX are assumed.",
        "w_legal_class_needs_review": "The legal class (VAT sale / non-residential) is uncertain.",
    },
    "pl": {
        "verdict": "Werdykt",
        "grade": "Ocena",
        "buy_at_asking": "Kup po cenie ofertowej",
        "negotiate": "Negocjuj",
        "pass": "Odpuść",
        "insufficient_data": "Za mało danych",
        "price": "Cena ofertowa",
        "max_bid": "Maksymalna cena (Max Bid)",
        "max_bid_none": "żadna cena nie spełnia progu",
        "hurdle": "Próg (docelowe IRR)",
        "irr": "IRR (10 lat, bez kredytu, po podatku)",
        "moic": "MOIC",
        "cagr": "CAGR",
        "gross_yield": "Rentowność brutto",
        "net_yield": "Rentowność netto",
        "sens_minus": "Max Bid przy wzroście cen niższym o 1 pp",
        "sens_plus": "Max Bid przy wzroście cen wyższym o 1 pp",
        "purchase": "Koszty zakupu",
        "pcc": "PCC",
        "notary": "Notariusz (z VAT)",
        "copies": "Wypisy aktu",
        "court": "Opłaty sądowe",
        "broker": "Pośrednik",
        "capex": "Remont (CAPEX)",
        "invested": "Łącznie zainwestowane",
        "years": "Przepływy w kolejnych latach",
        "year": "Rok",
        "rent": "Czynsz najmu",
        "costs": "Koszty",
        "tax": "Podatek dochodowy",
        "net": "Przepływ netto",
        "exit": "Sprzedaż po okresie",
        "exit_value": "Wartość sprzedaży",
        "selling": "Koszty sprzedaży",
        "sale_tax": "Podatek od sprzedaży",
        "proceeds": "Wpływ netto",
        "rent_basis": "Podstawa czynszu",
        "asking": "oparta na ofertach (porównania to stawki ofertowe; uwzględniono korektę)",
        "achieved": "faktycznie uzyskiwane czynsze",
        "notes": "Uwagi i ograniczenia",
        "confidence": "Pewność",
        "not_computed": "nie obliczono",
        "w_capex_prices_are_placeholders": (
            "Ceny remontu to wartości tymczasowe, nie dane rynkowe: nie opieraj się na tej wycenie."
        ),
        "w_rent_refused_too_few_comparables": "Za mało porównywalnych czynszów: nie wystawiono oceny.",
        "w_rent_thin_market": "Cienki rynek najmu: czynsz jest niepewny.",
        "w_vision_unavailable": "Zdjęcia nie zostały przeanalizowane: stan i remont są założone.",
        "w_legal_class_needs_review": "Klasa prawna (sprzedaż z VAT / lokal użytkowy) jest niepewna.",
    },
}


def _num(value: Decimal | int, lang: Lang) -> str:
    """The number exactly as the JSON has it, with grouping: en `450,000.00`, pl `450 000,00`."""
    text = format(value, "f")
    whole, _, frac = text.partition(".")
    sign = "-" if whole.startswith("-") else ""
    digits = whole.lstrip("-")
    groups: list[str] = []
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    grouped = ("," if lang == "en" else "\u00a0").join(reversed(groups)) or "0"
    return sign + grouped + (("." if lang == "en" else ",") + frac if frac else "")


def _opt(value: Decimal | None, lang: Lang, t: dict[str, str]) -> str:
    return _num(value, lang) if value is not None else t["not_computed"]


def render_markdown(analysis: DealAnalysis, lang: Lang = "pl") -> str:
    t = _T[lang]
    a = analysis

    def n(value: Decimal | int) -> str:
        return _num(value, lang)

    v = a.valuation
    r = a.cash_flow.returns
    lines = [f"# {a.listing.title or a.listing.otodom_id}", ""]
    where = " · ".join(x for x in (a.listing.city, a.listing.street) if x)
    lines += [f"{where} · {n(a.listing.area_m2)} m² · {a.listing.rooms}", ""] if where else []
    lines += [
        f"**{t['verdict']}: {t[v.verdict]}** · **{t['grade']}: {v.grade}** · "
        f"{t['confidence']}: {a.confidence.value}",
        "",
        f"- {t['price']}: {n(v.asking_price_pln)} PLN",
        f"- {t['max_bid']}: {n(v.max_bid_pln) + ' PLN' if v.max_bid_pln is not None else t['max_bid_none']}",
        f"- {t['sens_minus']}: {_opt(v.max_bid_if_appreciation_minus_1pp_pln, lang, t)}",
        f"- {t['sens_plus']}: {_opt(v.max_bid_if_appreciation_plus_1pp_pln, lang, t)}",
        f"- {t['hurdle']}: {n(v.hurdle)}",
        f"- {t['irr']}: {_opt(r.irr, lang, t)}",
        f"- {t['moic']}: {n(r.moic)} · {t['cagr']}: {_opt(r.cagr, lang, t)}",
        f"- {t['gross_yield']}: {n(r.gross_yield)} · {t['net_yield']}: {n(r.net_yield)}",
        f"- {t['rent_basis']}: {t[a.rent.basis]} ({n(a.rent.monthly_used_pln)} PLN)",
        "",
        f"## {t['purchase']}",
        "",
        f"- {t['pcc']}: {n(a.cash_flow.purchase.pcc_pln)}",
        f"- {t['notary']}: {n(a.cash_flow.purchase.notary_pln)}",
        f"- {t['copies']}: {n(a.cash_flow.purchase.deed_copies_pln)}",
        f"- {t['court']}: {n(a.cash_flow.purchase.court_fee_pln)}",
        f"- {t['broker']}: {n(a.cash_flow.purchase.broker_pln)}",
        f"- {t['capex']}: {n(a.capex_used_pln)}",
        f"- {t['invested']}: {n(a.cash_flow.total_invested_pln)}",
        "",
        f"## {t['years']}",
        "",
        f"| {t['year']} | {t['rent']} | {t['costs']} | {t['tax']} | {t['net']} |",
        "|---:|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {y.year} | {n(y.rent_collected_pln)} | {n(y.costs.total_pln)} | "
        f"{n(y.income_tax_pln)} | {n(y.net_cash_flow_pln)} |"
        for y in a.cash_flow.years
    ]
    ex = a.cash_flow.exit
    lines += [
        "",
        f"## {t['exit']}",
        "",
        f"- {t['exit_value']}: {n(ex.exit_value_pln)}",
        f"- {t['selling']}: {n(ex.selling_costs_pln)}",
        f"- {t['sale_tax']}: {n(ex.sale_tax_pln)}",
        f"- {t['proceeds']}: {n(ex.net_proceeds_pln)}",
    ]
    notes = [t[f"w_{w}"] for w in a.warnings if f"w_{w}" in t]
    if notes:
        lines += ["", f"## {t['notes']}", ""] + [f"- {x}" for x in notes]
    return "\n".join(lines) + "\n"
