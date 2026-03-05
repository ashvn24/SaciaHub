from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from requests import Session
from Models.utils.tokenmanage import token
from Models.utils.utils import util
from App.Models.Classes.token_authentication import decode_token
from Models import Classes
from Models.db import schemas
from Models.db import get_db
from typing import Optional
from Models.utils.error_handler import ErrorHandler
import logging
from typing import Dict
from fastapi import Query

logger = logging.getLogger(__name__)
error = ErrorHandler()

router = APIRouter(prefix="/v1/admin", tags=["Admin/User"])

@router.get("/bgvUsers/", operation_id="bgv-users")
def bgvUsers(
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
    Company_Portal_Url: str = None,
    pageNum: Optional[int] = None,
    own: Optional[int] = None,
    status: Optional[str] = None,
    filterBy: Optional[str] = Query(default=None)
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    util.is_admin(token_info)
    users = Classes.UserBGVManager(db, Company_Portal_Url).get_bgv_users(token_info, pageNum, own, status, filterBy)
    return users

@router.get("/bgvReport/", operation_id="bgv-report")
async def bgvReport(
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
    user: str = None,
    Company_Portal_Url: str = None,
    pageNum: Optional[int] = None,
    own: Optional[int] = None
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    util.is_admin(token_info)
    bgv_manager = Classes.UserBGVManager(db, Company_Portal_Url)
    await bgv_manager.create_bgv_report(user)
    users = bgv_manager.get_bgvreport(user)
    return users

@router.put("/bgvReport/", operation_id="bgv-report-update")
async def bgvReport(
    data: schemas.bgvReportSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    util.is_admin(token_info)
    users = Classes.UserBGVManager(db, data.Company_Portal_Url).update_bgv_report(data.User_ID, data.data)
    return users

@router.put("/bgv/status/", operation_id="bgv-status")
def bgv_status(
    data: schemas.bgvStatus,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try: 
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        util.is_admin(token_info)
        params = {"status": data.status}
        Classes.UserBGVManager(db, data.Company_Portal_Url).update_bgv_data(params, data.useruuid)
        db.commit()
        return JSONResponse(status_code=200, content={"message": f"status updated to {data.status}"})
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e