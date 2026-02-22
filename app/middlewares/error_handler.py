"""
Global exception handler middleware.
"""

from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger("middleware.error_handler")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions with standardized error format."""
    request_id = getattr(request.state, "request_id", "N/A") if hasattr(request, "state") else "N/A"
    logger.error(f"[{request_id}] Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "err_msg": "Internal server error",
            "status": 500,
            "time": datetime.now(timezone.utc).isoformat(),
            "type": "InternalError",
            "request_id": request_id,
        },
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle application-level exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )
