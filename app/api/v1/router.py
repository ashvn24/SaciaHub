"""
API v1 router aggregator.
Includes all endpoint routers with their original prefixes.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.admin import admin_router
from app.api.v1.endpoints.admin_bgv import bgv_router as admin_bgv_router
from app.api.v1.endpoints.admin_dashboard import admin_dashboard_router
from app.api.v1.endpoints.admin_timesheet import admin_timesheet_router
from app.api.v1.endpoints.admin_users import admin_users_router
from app.api.v1.endpoints.admin_violation import admin_violation_router
from app.api.v1.endpoints.company import company_router
from app.api.v1.endpoints.hr_bgv import hr_bgv_router
from app.api.v1.endpoints.hr_dashboard import hr_dashboard_router
from app.api.v1.endpoints.manager import manager_router
from app.api.v1.endpoints.notification import notification_router
from app.api.v1.endpoints.user import user_router

api_router = APIRouter()

# Admin routes
api_router.include_router(admin_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_bgv_router)
api_router.include_router(admin_timesheet_router)
api_router.include_router(admin_dashboard_router)
api_router.include_router(admin_violation_router)

# HR routes
api_router.include_router(hr_bgv_router)
api_router.include_router(hr_dashboard_router)

# User routes
api_router.include_router(user_router)

# Company routes
api_router.include_router(company_router)

# Manager routes
api_router.include_router(manager_router)

# Notification routes (WebSocket)
api_router.include_router(notification_router)
