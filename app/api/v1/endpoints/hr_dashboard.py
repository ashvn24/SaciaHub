"""
HR dashboard endpoint.
Preserves original route path /v1/HR/Dashboard/.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.dependencies.auth import get_current_user
from app.models.database import get_db
from app.repositories.token import TokenRepository

logger = get_logger("api.hr_dashboard")

hr_dashboard_router = APIRouter(prefix="/v1/HR", tags=["HR"])


@hr_dashboard_router.get("/Dashboard/")
async def get_dashboard_data(
    Company_portal_Url: str,
    token_info: dict = Depends(get_current_user),
    type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from Models.Classes.Dashboard import get_hr_dashboard

    TokenRepository(db, Company_portal_Url).check_token(token_info["Id"])
    return get_hr_dashboard(db, Company_portal_Url, token_info, type)
