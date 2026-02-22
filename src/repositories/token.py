"""
Token repository - handles auth token persistence and validation per tenant.
"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.core.exceptions import BadRequestException, NotFoundException
from src.core.logging import get_logger
from src.repositories.base import BaseRepository
from src.repositories.tenant import TenantRepository

logger = get_logger("repository.token")


class TokenRepository(BaseRepository):
    """Repository for user token operations across tenant schemas."""

    def __init__(self, db: Session, company_portal_url: str):
        super().__init__(db)
        tenant_repo = TenantRepository(db)
        self.tenant = tenant_repo.get_by_portal_url(company_portal_url)
        self.user_table = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_user_info"

    def get_user_details(self, uuid: str) -> Dict[str, Any]:
        """Get user details by UUID."""
        query = f'SELECT * FROM {self.user_table} WHERE "UserUUID" = :useruuid'
        result = self.execute_select(query, {"useruuid": uuid})
        if not result:
            raise NotFoundException("User")
        return result[0]

    def update_token(self, uuid: str, token: Optional[str]) -> None:
        """Update the user's auth token."""
        query = f'UPDATE {self.user_table} SET "authtoken" = :token WHERE "UserUUID" = :useruuid'
        self.execute_write(query, {"useruuid": uuid, "token": token})

    def check_token(self, uuid: str) -> None:
        """Check if user has a valid token (not None). Raises BadRequestException."""
        user = self.get_user_details(uuid)
        if user and user["authtoken"] is None:
            raise BadRequestException("invalid token")
