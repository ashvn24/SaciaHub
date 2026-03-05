import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from requests import Session
from Models.utils.tokenmanage import token
from App.Models.Classes.token_authentication import decode_token
from Models import Classes
from Models.db import schemas
from Models.db import get_db
from Models.utils.error_handler import ErrorHandler
from App.Models.Classes.AdminUserManager import UserManager
from App.Models.Classes.UserManager import UserAuthManager


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin", tags=["Admin/User"])
error = ErrorHandler()

@router.patch("/status/", operation_id="update-user-status")
async def update_user_status_route(
    ID: str,
    Company_Portal_Url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    cp = Company_Portal_Url
    uid = token_info["Id"]
    tk = token(db, cp)
    um = UserManager(db)
    
    tk.checktoken(uid)
    return await um.update_user_status(ID, Company_Portal_Url, token_info)


@router.post("/register/", operation_id="user-register")
async def user_register_route(
    data: schemas.BritsUserSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    cp = data.Company_Portal_Url
    uid = token_info["Id"]
    tk = token(db, cp)
    um = UserManager(db)
    
    tk.checktoken(uid)
    return await um.register_user(data, token_info)

@router.get("/impersonate/", operation_id="impersonate-user")
async def  ImpersonateRole(
    Company_Portal_Url: str,
    userID: int,
    token_info = Depends(decode_token),
    db: Session = Depends(get_db)
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    user = UserAuthManager(db, Company_Portal_Url)
    return user.impersonate_role(Company_Portal_Url, token_info, userID)

@router.post("/user/report/", operation_id="user-report")
async def report_user(
    data: schemas.UserReportSchema,
    token_info = Depends(decode_token),
    db: Session = Depends(get_db)
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    
@router.get("/getUsers/", operation_id="get-users")
async def getUSers(
    company_portal_url: str,
    token_info=Depends(decode_token),
    userID: Optional[int] = None,
    sortby: Optional[str] = None,
    db: Session = Depends(get_db),
    pagenum: Optional[int] = None,
    own: Optional[int] = None,
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
    filterBy: Optional[str] = None,
):
    try:
        token(db, company_portal_url).checktoken(token_info["Id"])
        user = Classes.GetUser(db, company_portal_url)
        users = user.get_all_users(token_info, userID, sortby, pagenum, own, sortBy, order, filterBy)
        return users
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

@router.delete("/deleteUser/", operation_id="delete-user")
async def deleteUser(
    data: schemas.DeleteUser,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        user = Classes.GetUser(db, data.Company_Portal_Url)
        users = user.delete_users(data.User_ID, token_info)
        return users
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e
        
@router.put("/updateUser/", operation_id="update-user")
async def updateUser(
    data: schemas.BritsUserSchema,
    UserID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        user = UserManager(db)
        users = user.update_user(UserID, data, token_info)
        return users
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e
    