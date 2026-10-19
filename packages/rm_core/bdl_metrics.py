"""Reviewed GUS BDL metric registry (RM-48): which variables Renti reads, what they mean and how they publish.

LEGAL[third-party-data]: reads public GUS BDL statistics; source terms, attribution and redistribution
limits are with counsel (B-012). Every metric shown carries its source, year and level (RM-48).
GDPR[personal-data]: none; aggregate territorial statistics only (RM-48).

Selection, directions and thresholds are the delegated analytical policy of the owner decisions of
2026-10-19 (section 7, B-023): chosen from the reference project's candidate list and **verified against the
live service on 2026-10-20** (variable id, unit and years from `/variables/{id}`, level availability and
attribute meanings from `/data/by-variable/{id}` and `/attributes`). Nothing was copied from the reference
project's files.

Rules of the registry:
- `unit` is BDL's own measure-unit string, because the validator compares it with the live answer;
  `unit_label_pl` is what a person reads. BDL counts are in unit "-".
- A metric is published natively at its source level (gmina or powiat); BDL also publishes its own
  aggregates at powiat, voivodeship and country level, which are read as published, never rebuilt.
- Powiat-grain metrics (deed transactions, deed median price, earnings, standard unemployment) have no gmina
  value: a gmina view shows the powiat figure as a proxy, labelled as such, never as the gmina's own.
- Prices here are **deed** statistics (invariant 2): they are never blended with Otodom asking rents.
- `direction` is `neutral` unless the favourable end is unambiguous; size, stock and price orderings say
  higher/lower. None of these metrics feeds the financial engine (invariant 4).
- Attribute handling: `1` is a value; `91` ("x": confidential or no information, placeholder 0) is suppressed;
  anything else (for example `3`, an aggregate that may be incomplete) is not used.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from rm_contracts.location_context import (
    ChangeBasis,
    Direction,
    MetricDefinition,
    PublicationPolicy,
    SelectionStatus,
    TerritoryLevel,
)

G, P, W, C = (
    TerritoryLevel.gmina,
    TerritoryLevel.powiat,
    TerritoryLevel.wojewodztwo,
    TerritoryLevel.country,
)
VERSION: Final = 1
HISTORY_YEARS: Final = 10  # years of trend read per metric, ending at the latest year the source has
VALID_ATTR_IDS: Final = frozenset({1})
SUPPRESSED_ATTR_IDS: Final = frozenset({91})
DEFAULT_MIN_COVERAGE: Final = Decimal("0.90")
MIN_COHORT: Final = 10

FAMILIES: Final = {
    "population": "Ludność i wiek",
    "movement": "Ruch ludności",
    "housing": "Budownictwo i zasoby mieszkaniowe",
    "market": "Transakcje na rynku lokali (akty notarialne)",
    "labour": "Rynek pracy i dochody",
    "business": "Przedsiębiorczość",
    "fiscal": "Dochody gmin",
}


@dataclass(frozen=True)
class MetricSpec:
    key: str
    variable_id: int
    name_pl: str
    family: str
    unit: str  # BDL measureUnitName
    unit_label_pl: str
    native: TerritoryLevel
    direction: Direction = Direction.neutral
    change: ChangeBasis = ChangeBasis.percent
    additive: bool = False
    min_value: Decimal | None = Decimal(0)
    max_value: Decimal | None = None
    min_coverage: Decimal = DEFAULT_MIN_COVERAGE  # lower where the source withholds small cells
    min_cohort: int = MIN_COHORT
    note_pl: str = ""

    @property
    def published_levels(self) -> frozenset[TerritoryLevel]:
        return frozenset({G, P, W, C}) if self.native is G else frozenset({P, W, C})

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            key=self.key,
            version=VERSION,
            name_pl=self.name_pl,
            unit=self.unit,
            native_level=self.native,
            published_levels=self.published_levels,
            direction=self.direction,
            change_basis=self.change,
            additive=self.additive,
            min_value=self.min_value,
            max_value=self.max_value,
            selection=SelectionStatus.selected,
            bdl_variable_id=str(self.variable_id),
        )

    @property
    def policy(self) -> PublicationPolicy:
        return PublicationPolicy(
            metric_key=self.key,
            metric_version=VERSION,
            min_coverage=self.min_coverage,
            min_cohort_size=self.min_cohort,
        )


def _spec(*args: object, **kw: object) -> MetricSpec:
    return MetricSpec(*args, **kw)  # type: ignore[arg-type]


HIGHER, LOWER = Direction.higher_is_favorable, Direction.lower_is_favorable
SIGNED = ChangeBasis.absolute
PERCENT_0_100 = {"max_value": Decimal(100)}

METRICS: Final[tuple[MetricSpec, ...]] = (
    _spec("population_total", 72305, "Ludność ogółem", "population", "osoba", "osób", G, additive=True),
    _spec(
        "population_pre_working_age",
        149,
        "Ludność w wieku przedprodukcyjnym",
        "population",
        "osoba",
        "osób",
        G,
        additive=True,
    ),
    _spec(
        "population_working_age",
        152,
        "Ludność w wieku produkcyjnym",
        "population",
        "osoba",
        "osób",
        G,
        additive=True,
    ),
    _spec(
        "population_post_working_age",
        155,
        "Ludność w wieku poprodukcyjnym",
        "population",
        "osoba",
        "osób",
        G,
        additive=True,
    ),
    _spec(
        "net_migration",
        1365234,
        "Saldo migracji na pobyt stały",
        "movement",
        "osoba",
        "osób",
        G,
        direction=HIGHER,
        change=SIGNED,
        additive=True,
        min_value=None,
        note_pl="Wartość ze znakiem: napływ minus odpływ.",
    ),
    _spec(
        "natural_increase",
        68,
        "Przyrost naturalny",
        "movement",
        "-",
        "osób",
        G,
        direction=HIGHER,
        change=SIGNED,
        additive=True,
        min_value=None,
        note_pl="Wartość ze znakiem: urodzenia minus zgony.",
    ),
    _spec(
        "dwellings_completed",
        748601,
        "Mieszkania oddane do użytkowania",
        "housing",
        "-",
        "mieszkań",
        G,
        additive=True,
        note_pl="Aktywność budowlana, nie ocena rynku.",
    ),
    _spec(
        "dwellings_completed_floor_area",
        748603,
        "Powierzchnia użytkowa mieszkań oddanych do użytkowania",
        "housing",
        "m2",
        "m²",
        G,
        additive=True,
    ),
    _spec("dwelling_stock", 60811, "Zasoby mieszkaniowe", "housing", "-", "mieszkań", G, additive=True),
    _spec(
        "building_permits_dwellings",
        1641096,
        "Mieszkania w pozwoleniach na budowę (rok)",
        "housing",
        "-",
        "mieszkań",
        G,
        additive=True,
        note_pl="Wiersz roczny danych kwartalnych; okresów narastających nie sumujemy.",
    ),
    _spec(
        "dwelling_transactions_count",
        633097,
        "Transakcje kupna-sprzedaży lokali mieszkalnych",
        "market",
        "szt.",
        "transakcji",
        P,
        additive=True,
        min_coverage=Decimal("0.70"),
        note_pl="Poziom powiatu; GUS utajnia małe komórki. Ceny z aktów notarialnych, nie ceny ofertowe.",
    ),
    _spec(
        "dwelling_median_price_m2",
        1607914,
        "Mediana cen za 1 m² lokali mieszkalnych",
        "market",
        "zł",
        "zł/m²",
        P,
        min_coverage=Decimal("0.70"),
        note_pl="Poziom powiatu; ceny z aktów notarialnych (deed), nigdy nie mieszane z cenami ofertowymi.",
    ),
    _spec(
        "average_monthly_gross_earnings",
        64428,
        "Przeciętne miesięczne wynagrodzenie brutto",
        "labour",
        "zł",
        "zł",
        P,
        direction=HIGHER,
        note_pl="Poziom powiatu; nie jest dochodem gospodarstwa domowego pod danym adresem.",
    ),
    _spec(
        "unemployment_rate_standard",
        60270,
        "Stopa bezrobocia rejestrowanego",
        "labour",
        "%",
        "%",
        P,
        direction=LOWER,
        change=SIGNED,
        **PERCENT_0_100,
        note_pl="Poziom powiatu; mianownik to ludność aktywna zawodowo.",
    ),
    _spec(
        "unemployment_share_working_age",
        79214,
        "Udział bezrobotnych zarejestrowanych w ludności w wieku produkcyjnym",
        "labour",
        "%",
        "%",
        G,
        direction=LOWER,
        change=SIGNED,
        **PERCENT_0_100,
        note_pl="Inny mianownik niż stopa bezrobocia rejestrowanego dla powiatu.",
    ),
    _spec(
        "regon_entities_total",
        152702,
        "Podmioty gospodarki narodowej w rejestrze REGON",
        "business",
        "-",
        "podmiotów",
        G,
        additive=True,
    ),
    _spec(
        "regon_entities_per_10k",
        60530,
        "Podmioty REGON na 10 tys. mieszkańców",
        "business",
        "-",
        "podmiotów/10 tys. mieszk.",
        G,
        direction=HIGHER,
    ),
    _spec(
        "property_tax_revenue",
        76077,
        "Dochody gminy z podatku od nieruchomości",
        "fiscal",
        "zł",
        "zł",
        G,
        additive=True,
        note_pl="Wpływy budżetu gminy, nie obciążenie podatkowe mieszkańca ani lokalu.",
    ),
    _spec(
        "municipal_pit_revenue",
        76046,
        "Udziały gminy w podatku dochodowym od osób fizycznych (PIT)",
        "fiscal",
        "zł",
        "zł",
        G,
        additive=True,
        note_pl="Wpływ do budżetu gminy, nie dochód mieszkańców.",
    ),
    _spec(
        "municipal_cit_revenue",
        76043,
        "Udziały gminy w podatku dochodowym od osób prawnych (CIT)",
        "fiscal",
        "zł",
        "zł",
        G,
        additive=True,
        note_pl="Wpływ do budżetu gminy.",
    ),
    _spec(
        "pit_revenue_per_resident",
        149128,
        "Dochody gminy z PIT na 1 mieszkańca",
        "fiscal",
        "zł",
        "zł/mieszk.",
        G,
        direction=HIGHER,
    ),
    _spec(
        "own_revenue_per_resident",
        76976,
        "Dochody własne gminy na 1 mieszkańca",
        "fiscal",
        "zł",
        "zł/mieszk.",
        G,
        direction=HIGHER,
        note_pl="Szersze niż dochody podatkowe; miasta na prawach powiatu mają też zadania powiatu.",
    ),
)

BY_KEY: Final = {m.key: m for m in METRICS}
BY_VARIABLE: Final = {str(m.variable_id): m for m in METRICS}
DEFINITIONS: Final = {m.key: m.definition for m in METRICS}
POLICIES: Final = {m.key: m.policy for m in METRICS}
