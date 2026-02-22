"""Common schema utilities and base models."""

from datetime import date, datetime
from uuid import UUID


def serialize_row(row):
    """Convert a SQLAlchemy row to a serializable dictionary."""
    return {
        column: (value.isoformat() if isinstance(value, (date, datetime)) else value)
        for column, value in row._mapping.items()
    }
