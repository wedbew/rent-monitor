"""Declarative base, naming convention and enum helper shared by every model (blueprint §3)."""

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import DateTime, Enum, MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

SCHEMA = "app"
APP = {"schema": SCHEMA}

# Deterministic constraint names keep Alembic diffs stable. `ck` needs an explicit constraint name.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING, schema=SCHEMA)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True), dict[str, Any]: JSONB}


def _values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Native Postgres enum in schema `app`, stored by value."""
    return Enum(enum_cls, name=name, schema=SCHEMA, values_callable=_values)
