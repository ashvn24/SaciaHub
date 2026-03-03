"""
Base repository with common database operations.
All repositories inherit from this for DRY database access.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.core.exceptions import DatabaseException
from src.core.logging import get_logger

logger = get_logger("repository.base")


class BaseRepository:
    """Base repository providing common DB operations."""

    def __init__(self, db: Session):
        self.db = db

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None, fetch: bool = True
    ) -> Optional[List[Dict]]:
        """Execute a raw SQL query with parameterized values."""
        try:
            result = self.db.execute(text(query), params or {})
            if fetch:
                return [dict(row) for row in result.mappings().all()]
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Query execution failed: {e}")
            raise DatabaseException(str(e))

    def execute_select(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Execute a SELECT query and return results."""
        result = self.db.execute(text(query), params or {})
        return [dict(row) for row in result.mappings().all()]

    def execute_write(self, query: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Execute an INSERT/UPDATE/DELETE query."""
        try:
            self.db.execute(text(query), params or {})
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Write operation failed: {e}")
            raise DatabaseException(str(e))

    def execute_select_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Execute a SELECT query and return a single result."""
        result = self.db.execute(text(query), params or {})
        row = result.mappings().first()
        return dict(row) if row else None
