"""
Standardized response helpers.
"""

from typing import Any, Dict


def success_response(message: str, data: Any = None) -> Dict:
    """Create a standardized success response."""
    response = {"status_code": 200, "detail": message}
    if data is not None:
        response["content"] = data
    return response


def error_response(message: str, status_code: int = 400) -> Dict:
    """Create a standardized error response."""
    return {"status_code": status_code, "detail": message}
