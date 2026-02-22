"""
Admin BGV management endpoints.
Preserves all original route paths under /v1/admin.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.models.database import get_db
from app.repositories.token import TokenRepository
from app.schemas.bgv import bgvReportSchema, bgvStatus

logger = get_logger("api.admin_bgv")

bgv_router = APIRouter(prefix="/v1/admin", tags=["Admin/User"])


def _check_token(db: Session, portal_url: str, user_id: str) -> None:
    TokenRepository(db, portal_url).check_token(user_id)


@bgv_router.get("/bgvUsers/", operation_id="bgv-users")
def bgv_users(
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
    Company_Portal_Url: str = None,
    pageNum: Optional[int] = None,
    own: Optional[int] = None,
    status: Optional[str] = None,
    filterBy: Optional[str] = Query(default=None),
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    require_admin(token_info)
    return UserBGVManager(db, Company_Portal_Url).get_bgv_users(token_info, pageNum, own, status, filterBy)


@bgv_router.get("/bgvReport/", operation_id="bgv-report")
async def bgv_report(
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
    user: str = None,
    Company_Portal_Url: str = None,
    pageNum: Optional[int] = None,
    own: Optional[int] = None,
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    require_admin(token_info)
    bgv_manager = UserBGVManager(db, Company_Portal_Url)
    await bgv_manager.create_bgv_report(user)
    return bgv_manager.get_bgvreport(user)


@bgv_router.put("/bgvReport/", operation_id="bgv-report-update")
async def update_bgv_report(
    data: bgvReportSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    require_admin(token_info)
    return UserBGVManager(db, data.Company_Portal_Url).update_bgv_report(data.User_ID, data.data)


@bgv_router.put("/bgv/status/", operation_id="bgv-status")
def bgv_status_update(
    data: bgvStatus,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    require_admin(token_info)
    params = {"status": data.status}
    UserBGVManager(db, data.Company_Portal_Url).update_bgv_data(params, data.useruuid)
    db.commit()
    return JSONResponse(status_code=200, content={"message": f"status updated to {data.status}"})
