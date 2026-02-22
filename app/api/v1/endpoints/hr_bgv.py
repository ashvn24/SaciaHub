"""
HR BGV endpoints.
Preserves original route paths under /v1/HR/bgv/.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.models.database import get_db
from app.repositories.token import TokenRepository

logger = get_logger("api.hr_bgv")

hr_bgv_router = APIRouter(prefix="/v1/HR/bgv", tags=["HR"])


@hr_bgv_router.get("/get-info/")
async def getbgvinfo(
    Company_portal_Url: str,
    uuid: str,
    token_info: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.userbgvManager import UserBGVManager

    require_admin(token_info)
    TokenRepository(db, Company_portal_Url).check_token(token_info["Id"])
    us = GetUser(db, Company_portal_Url)
    bg = UserBGVManager(db, Company_portal_Url)

    if us.get_userdetails_by_uuid(uuid):
        return bg.get_user_bgv(uuid)


@hr_bgv_router.put("/update-info/")
async def update_bgv_info(
    Company_portal_Url: str,
    data: dict,
    uuid: str,
    token_info: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.userbgvManager import UserBGVManager
    from Models.db import schemas

    require_admin(token_info)
    TokenRepository(db, Company_portal_Url).check_token(token_info["Id"])
    us = GetUser(db, Company_portal_Url)
    bg = UserBGVManager(db, Company_portal_Url)

    if us.get_userdetails_by_uuid(uuid):
        rdata = bg.prepare_update_data(data)
        bg.update_bgv_data(rdata, uuid)
        bg.update_verification_results(data, uuid)
        bg.insert_bgv_master(uuid)
        return {"message": "bgv-updated"}
    else:
        return {"message": "error occurred"}
