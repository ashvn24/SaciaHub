"""
Admin violation endpoints.
Preserves original route paths under /v1/admin/violation.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_admin
from app.models.database import get_db
from app.repositories.token import TokenRepository
from app.schemas.violation import violationSchema
from app.utils.response import success_response

logger = get_logger("api.admin_violation")

admin_violation_router = APIRouter(prefix="/v1/admin/violation", tags=["Admin/Violation"])


def _check_token(db: Session, portal_url: str, user_id: str) -> None:
    TokenRepository(db, portal_url).check_token(user_id)


@admin_violation_router.post("/report/", operation_id="violation-report")
async def report_user(
    data: violationSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.UserManager import UserAuthManager
    from Models.Classes.userbgvManager import UserBGVManager
    from Models.Classes.violation import violation

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    require_admin(token_info)

    vl = violation(db, data.Company_Portal_Url)
    user = GetUser(db, data.Company_Portal_Url)
    bgv = UserBGVManager(db, data.Company_Portal_Url)
    uinfo = UserAuthManager(db, data.Company_Portal_Url)

    result = user.get_userdetails_by_uuid(data.Useruuid)
    if result:
        ins = vl.add_violation(data)
        params = {"status": "Rejected"}
        modules = ["Applications"]
        bgv.update_bgv_data(params, data.Useruuid)
        uinfo.update_modules(data.Useruuid, modules)
    if ins:
        return JSONResponse(status_code=200, content={"message": "violation reported"})


@admin_violation_router.get("/get-report/", operation_id="get-violation")
async def get_violation(
    Company_Portal_Url: str,
    useruuid: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.violation import violation

    _check_token(db, Company_Portal_Url, token_info["Id"])
    require_admin(token_info)

    user = GetUser(db, Company_Portal_Url)
    vl = violation(db, Company_Portal_Url)

    result = user.get_userdetails_by_uuid(useruuid)
    if not result:
        return {"status_code": 400, "detail": "user not found"}

    vdata = vl.get_violation(useruuid)
    if not vdata:
        return {"status_code": 400, "detail": "Error occured"}

    res = success_response("violation results")
    res["content"] = vdata
    return res
