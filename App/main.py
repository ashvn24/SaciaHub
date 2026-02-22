from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
import sentry_sdk
import logging
import logging.config
import os
from typing import List
from functools import lru_cache

# Route imports
# from route.adminManagement.adminroute import admin_router
from route import apiroute
from route.company_management.company_manage import company_router
from route.user_management.user_manage import user_router
from route.managerRoute.managerRoute import manager_router
from route.Notification.channels import notification_router
from route.adminManagement.adminroute import admin_router
from Models.db.db_connection import engine
class Settings:
    """Application settings and configuration."""
    
    def __init__(self):
        self.SENTRY_DSN: str = "https://5a0a197c4fd6fba011e8b7a1218e0b9d@o4507693319389184.ingest.us.sentry.io/4507693320699904"
        self.ENVIRONMENT: str = "development"  # Change to "production" for prod
        self.ALLOWED_ORIGINS: List[str] = ["*"]  # Configure specific origins in production
        self.SECRET_KEY: str = "your-super-secret-key-here"  # Change this in production
        self.LOG_LEVEL: str = "INFO"

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

def setup_logging() -> logging.Logger:
    """Configure logging with rotation and multiple handlers."""
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "default",
                "filename": "app.log",
                "when": "midnight",  # Rotate logs daily at midnight
                "backupCount": 7,    # Keep 7 days' worth of logs
            },
        },
        "loggers": {
            "": {  # root logger
                "level": "INFO",
                "handlers": ["console", "file"],
            },
            "myapp": {
                "level": "DEBUG",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    logging.config.dictConfig(logging_config)
    return logging.getLogger(__name__)

def init_sentry() -> None:
    """Initialize Sentry SDK."""
    settings = get_settings()
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
        profiles_sample_rate=1.0 if settings.ENVIRONMENT == "development" else 0.1,
    )

class StatusCodeMiddleware(BaseHTTPMiddleware):
    """Middleware to log response status codes."""
    
    def __init__(self, app, logger: logging.Logger):
        super().__init__(app)
        self.logger = logger

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        self.logger.info(
            f"Request: {request.method} {request.url.path} - Status: {response.status_code}"
        )
        request.state.status_code = response.status_code
        return response

def create_app() -> FastAPI:
    """Application factory pattern for FastAPI instance."""
    settings = get_settings()
    logger = setup_logging()
    # init_sentry()

    app = FastAPI()

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Authorization", "Refresh-Token"],
    )

    # Add custom middleware
    app.add_middleware(StatusCodeMiddleware, logger=logger)

    # Include routers with prefixes
    routers = [
        apiroute,
        company_router,
        user_router,
        notification_router,
        manager_router,
        admin_router
    ]
    # app.include_router(app)
    for router in routers:
        app.include_router(router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.get("/", tags=["DigiLocker Callback"])
    async def digilocker_callback(request: Request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code:
            return {"error": "Authorization code missing"}
        return {"auth_code": code, "state": state}

    return app

def init_db():
    try:
        engine.connect()
        print("connected Successfully")
    except Exception as e:
        raise e


# Create the application instance
app = create_app()

@app.on_event("startup")
async def on_startup():
    """Initialize DB or other resources."""
    init_db()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if get_settings().ENVIRONMENT == "development" else False,
        log_level="info",
    )