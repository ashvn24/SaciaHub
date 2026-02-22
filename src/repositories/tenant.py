"""
Tenant repository - handles all tenant/schema resolution.
Central place for tenant lookup used across all domains.
"""

from typing import Optional

from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundException
from src.core.logging import get_logger
from src.models.master import TenantInfo
from src.repositories.base import BaseRepository

logger = get_logger("repository.tenant")


class TenantRepository(BaseRepository):
    """Repository for tenant operations."""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_portal_url(self, portal_url: str) -> TenantInfo:
        """Get tenant info by portal URL. Raises NotFoundException if not found."""
        tenant = (
            self.db.query(TenantInfo)
            .filter(TenantInfo.PortalURL == portal_url)
            .first()
        )
        if tenant is None:
            raise NotFoundException("Schema")
        return tenant

    def get_by_shortname(self, shortname: str) -> Optional[TenantInfo]:
        """Get tenant info by short name."""
        return (
            self.db.query(TenantInfo)
            .filter(TenantInfo.ShortName == shortname)
            .first()
        )

    def get_by_email(self, email: str) -> Optional[TenantInfo]:
        """Get tenant info by contact email."""
        return (
            self.db.query(TenantInfo)
            .filter(TenantInfo.ContactEmail == email)
            .first()
        )

    def create(self, tenant: TenantInfo) -> TenantInfo:
        """Create a new tenant record."""
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update_status(self, tenant: TenantInfo, status: str) -> TenantInfo:
        """Update tenant status."""
        tenant.TenantStatus = status
        self.db.commit()
        return tenant

    def get_table_name(self, tenant: TenantInfo, table_suffix: str) -> str:
        """Build a fully qualified table name for a tenant."""
        return f"{tenant.SchemaName}.tb_{tenant.ShortName}_{table_suffix}"
