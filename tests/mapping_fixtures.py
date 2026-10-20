"""Hand-built territorial reference with the naming patterns seen live on 2026-10-20 (invented ids)."""

from rm_contracts.location_context import TerritoryLevel as L
from rm_contracts.location_context import TerritoryRef

COUNTRY = TerritoryRef(territory_id="PL", teryt="", name="POLSKA", level=L.country)
W12 = TerritoryRef(territory_id="W12", teryt="12", name="Małopolskie", level=L.wojewodztwo, parent_id="PL")
W14 = TerritoryRef(territory_id="W14", teryt="14", name="Mazowieckie", level=L.wojewodztwo, parent_id="PL")
W04 = TerritoryRef(
    territory_id="W04", teryt="04", name="Kujawsko-Pomorskie", level=L.wojewodztwo, parent_id="PL"
)


def powiat(pid: str, teryt: str, name: str, parent: str) -> TerritoryRef:
    return TerritoryRef(territory_id=pid, teryt=teryt, name=name, level=L.powiat, parent_id=parent)


def gmina(gid: str, teryt: str, name: str, parent: str) -> TerritoryRef:
    return TerritoryRef(territory_id=gid, teryt=teryt, name=name, level=L.gmina, parent_id=parent)


REF = [
    COUNTRY,
    W12,
    W14,
    W04,
    powiat("P1201", "1201", "Powiat bocheński", "W12"),
    powiat("P1261", "1261", "Powiat m. Kraków", "W12"),
    powiat("P1206", "1206", "Powiat krakowski", "W12"),
    powiat("P1465", "1465", "Powiat m. st. Warszawa", "W14"),
    powiat("P0401", "0401", "Powiat bydgoski", "W04"),
    gmina("G1", "1201011", "Bochnia", "P1201"),  # urban
    gmina("G2", "1201022", "Bochnia", "P1201"),  # rural: same name, same powiat
    gmina("G3", "1201033", "Nowy Wiśnicz", "P1201"),
    gmina("G4", "1261011", "Kraków", "P1261"),
    gmina("G5", "1206013", "Krzeszowice", "P1206"),
    gmina("G6", "1465011", "Warszawa", "P1465"),
    gmina("G7", "0401013", "Koronowo", "P0401"),
]
