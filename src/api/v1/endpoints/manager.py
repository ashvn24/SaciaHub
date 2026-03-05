"""
Manager endpoints.
Preserves original route path /v1/manager/Dashboard/.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.dependencies.auth import get_current_user
from src.models.database import get_db

logger = get_logger("api.manager")

manager_router = APIRouter(prefix="/v1/manager", tags=["Manager"])


@manager_router.get("/Dashboard/")
async def get_dashboard_data(
    Company_portal_Url: str,
    token_info: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from App.Models.Classes.Dashboard import ManagerDashboardExtension

    dashboard = ManagerDashboardExtension(db, Company_portal_Url, token_info)
    return dashboard.get_manager_dashboard_data()
