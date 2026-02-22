"""
Centralized exception classes and standardized error responses.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException


class AppException(HTTPException):
    """Base application exception with standardized error format."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str = "AppError",
        detail: Any = None,
    ):
        error_body = {
            "err_msg": message,
            "status": status_code,
            "time": datetime.now(timezone.utc).isoformat(),
            "type": error_type,
        }
        if detail:
            error_body["detail"] = detail
        super().__init__(status_code=status_code, detail=error_body)


class NotFoundException(AppException):
    def __init__(self, resource: str = "Resource", detail: Any = None):
        super().__init__(404, f"{resource} not found", "NotFound", detail)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", detail: Any = None):
        super().__init__(401, message, "Unauthorized", detail)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", detail: Any = None):
        super().__init__(403, message, "Forbidden", detail)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", detail: Any = None):
        super().__init__(400, message, "BadRequest", detail)


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict", detail: Any = None):
        super().__init__(409, message, "Conflict", detail)


class DatabaseException(AppException):
    def __init__(self, message: str = "Database error", detail: Any = None):
        super().__init__(500, message, "DatabaseError", detail)


class TokenExpiredException(UnauthorizedException):
    def __init__(self):
        super().__init__("Token has expired")


class TokenRevokedException(UnauthorizedException):
    def __init__(self):
        super().__init__("Token has been revoked")


class InvalidTokenException(UnauthorizedException):
    def __init__(self):
        super().__init__("Session expired")


class InsufficientPermissionsException(ForbiddenException):
    def __init__(self):
        super().__init__("You do not have the permission to perform this action")
