"""
Authentication dependencies for FastAPI.
"""

from typing import Dict, Optional

from fastapi import Header

from app.core.exceptions import UnauthorizedException
from app.core.security import decode_jwt_token


async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict:
    """FastAPI dependency: decode and validate JWT from Authorization header."""
    if not authorization:
        raise UnauthorizedException("Authorization header missing")
    token = authorization.split(" ")[1] if " " in authorization else authorization
    return decode_jwt_token(token)


async def validate_token(authorization: Optional[str] = Header(None)) -> Dict:
    """Alias for get_current_user - maintains backward compatibility with existing code."""
    if authorization is None:
        raise UnauthorizedException("Authorization header missing")
    token = authorization.split(" ")[1] if " " in authorization else authorization
    return decode_jwt_token(token)
