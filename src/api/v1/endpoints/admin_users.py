"""
Admin user management endpoints.
Preserves all original route paths under /v1/admin.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.dependencies.auth import get_current_user
from src.models.database import get_db
from src.repositories.token import TokenRepository
from src.schemas.user import BritsUserSchema, DeleteUser, UserReportSchema

logger = get_logger("api.admin_users")

admin_users_router = APIRouter(prefix="/v1/admin", tags=["Admin/User"])


def _check_token(db: Session, portal_url: str, user_id: str) -> None:
    TokenRepository(db, portal_url).check_token(user_id)


@admin_users_router.patch("/status/", operation_id="update-user-status")
async def update_user_status_route(
    ID: str,
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.AdminUserManager import UserManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    um = UserManager(db)
    return await um.update_user_status(ID, Company_Portal_Url, token_info)


@admin_users_router.post("/register/", operation_id="user-register")
async def user_register_route(
    data: BritsUserSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.AdminUserManager import UserManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    um = UserManager(db)
    return await um.register_user(data, token_info)


@admin_users_router.get("/impersonate/", operation_id="impersonate-user")
async def impersonate_role(
    Company_Portal_Url: str,
    userID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    user = UserAuthManager(db, Company_Portal_Url)
    return user.impersonate_role(Company_Portal_Url, token_info, userID)


@admin_users_router.post("/user/report/", operation_id="user-report")
async def report_user(
    data: UserReportSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_token(db, data.Company_Portal_Url, token_info["Id"])


@admin_users_router.get("/getUsers/", operation_id="get-users")
async def get_users(
    company_portal_url: str,
    token_info=Depends(get_current_user),
    userID: Optional[int] = None,
    sortby: Optional[str] = None,
    db: Session = Depends(get_db),
    pagenum: Optional[int] = None,
    own: Optional[int] = None,
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
    filterBy: Optional[str] = None,
):
    from Models.Classes.GetUser import GetUser

    _check_token(db, company_portal_url, token_info["Id"])
    user = GetUser(db, company_portal_url)
    return user.get_all_users(token_info, userID, sortby, pagenum, own, sortBy, order, filterBy)


@admin_users_router.delete("/deleteUser/", operation_id="delete-user")
async def delete_user(
    data: DeleteUser,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.GetUser import GetUser

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    user = GetUser(db, data.Company_Portal_Url)
    return user.delete_users(data.User_ID, token_info)


@admin_users_router.put("/updateUser/", operation_id="update-user")
async def update_user(
    data: BritsUserSchema,
    UserID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.AdminUserManager import UserManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    user = UserManager(db)
    return user.update_user(UserID, data, token_info)
