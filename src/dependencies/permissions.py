"""
Permission checking utilities.
"""

from typing import Dict

from src.core.exceptions import InsufficientPermissionsException

ADMIN_ROLES = {"Admin", "Manager", "HR"}


def require_admin(token_info: Dict) -> None:
    """Raise if user doesn't have admin/manager/HR role."""
    if token_info.get("role") not in ADMIN_ROLES:
        raise InsufficientPermissionsException()
