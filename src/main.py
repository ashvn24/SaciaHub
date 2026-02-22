"""
Application entry point with factory pattern.
Creates the FastAPI application with all middleware, routers, and lifecycle events.
"""

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.exceptions import AppException
from src.core.logging import setup_logging
from src.middlewares.error_handler import app_exception_handler, global_exception_handler
from src.middlewares.logging import LoggingMiddleware
from src.middlewares.request_id import RequestIDMiddleware

# Ensure legacy App directory is on the Python path for bridge imports
_legacy_app_dir = str(Path(__file__).resolve().parent.parent / "App")
if _legacy_app_dir not in sys.path:
    sys.path.insert(0, _legacy_app_dir)


def create_app() -> FastAPI:
    """Application factory: builds and configures the FastAPI instance."""
    settings = get_settings()
    logger = setup_logging()

    app = FastAPI(
        title=settings.PROJECT_TITLE,
        version=settings.PROJECT_VERSION,
        debug=settings.DEBUG,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Authorization", "Refresh-Token"],
    )

    # Custom middleware (order matters: outermost first)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Exception handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # API routes
    app.include_router(api_router)

    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    # DigiLocker OAuth callback (preserves legacy route)
    @app.get("/", tags=["DigiLocker Callback"])
    async def digilocker_callback(request: Request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code:
            return {"error": "Authorization code missing"}
        return {"auth_code": code, "state": state}

    return app


# Application instance
app = create_app()


@app.on_event("startup")
async def on_startup():
    """Verify database connection on startup."""
    from sqlalchemy import text

    from src.core.logging import get_logger
    from src.models.database import engine

    logger = get_logger("startup")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.APP_PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )
