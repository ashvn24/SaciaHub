"""
Token validation service.
Replaces the scattered token(db, url).checktoken(id) pattern.
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.token import TokenRepository

logger = get_logger("service.token")


class TokenService:
    """Service for token validation operations."""

    def __init__(self, db: Session, company_portal_url: str):
        self._repo = TokenRepository(db, company_portal_url)

    def validate_user_token(self, user_uuid: str) -> None:
        """Validate that the user has an active auth token."""
        self._repo.check_token(user_uuid)

    def get_user_details(self, user_uuid: str) -> dict:
        """Get user details by UUID."""
        return self._repo.get_user_details(user_uuid)

    def update_token(self, user_uuid: str, token: str) -> None:
        """Update the user's auth token."""
        self._repo.update_token(user_uuid, token)
