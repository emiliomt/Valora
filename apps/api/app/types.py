"""Portable column types shared across models."""

import uuid

from sqlalchemy import CHAR, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PGUUID


class GUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's native UUID type when available, otherwise stores as a
    32-character hex string (SQLite, used for local dev/tests per PRD 9
    "Use UUID primary keys").
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
