"""Shared ECB SDMX-CSV fixture builders for the risk-free tests (RM-210). Offline, no network."""

from __future__ import annotations

from rm_core.risk_free import ECB_SERIES_KEY

HEADER = (
    "KEY,FREQ,REF_AREA,IR_TYPE,TR_TYPE,MATURITY_CAT,BS_COUNT_SECTOR,CURRENCY_TRANS,IR_BUS_COV,IR_FV_TYPE,"
    "TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK,OBS_COM,TIME_FORMAT,BREAKS,COLLECTION,"
    "COMPILING_ORG,DISS_ORG,DOM_SER_IDS,PUBL_ECB,PUBL_MU,PUBL_PUBLIC,COMPILATION,COVERAGE,DECIMALS,"
    "NAT_TITLE,SOURCE_AGENCY,UNIT,UNIT_MULT"
)


def row(
    *,
    key: str = f"IRS.{ECB_SERIES_KEY}",
    freq: str = "M",
    period: str = "2026-09",
    value: str = "6.23",
    status: str = "A",
    unit: str = "PC",
    mult: str = "0",
) -> str:
    values = {
        "KEY": key,
        "FREQ": freq,
        "REF_AREA": "PL",
        "IR_TYPE": "L",
        "TR_TYPE": "L40",
        "MATURITY_CAT": "CI",
        "BS_COUNT_SECTOR": "0000",
        "CURRENCY_TRANS": "PLN",
        "IR_BUS_COV": "N",
        "IR_FV_TYPE": "Z",
        "TIME_PERIOD": period,
        "OBS_VALUE": value,
        "OBS_STATUS": status,
        "OBS_CONF": "F",
        "TIME_FORMAT": "P1M",
        "COLLECTION": "A",
        "UNIT": unit,
        "UNIT_MULT": mult,
    }
    return ",".join(values.get(name, "") for name in HEADER.split(","))


def csv_of(*rows: str) -> str:
    return "\n".join([HEADER, *rows]) + "\n"
