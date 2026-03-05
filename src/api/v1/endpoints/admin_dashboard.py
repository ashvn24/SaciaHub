"""
Admin dashboard endpoint.
Preserves original route path /v1/admin/dashboard/.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.dependencies.auth import get_current_user
from src.models.database import get_db
from src.repositories.token import TokenRepository

logger = get_logger("api.admin_dashboard")

admin_dashboard_router = APIRouter(prefix="/v1/admin", tags=["Admin"])


@admin_dashboard_router.post("/dashboard/", operation_id="admin-dashboard")
def admin_dashboard(
    Company_portal_Url: str,
    token_info: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from App.Models.Classes.Dashboard import AdminDashboard

    TokenRepository(db, Company_portal_Url).check_token(token_info["Id"])
    dashb = AdminDashboard(db, Company_portal_Url, token_info)
    return dashb.admindashboard()
