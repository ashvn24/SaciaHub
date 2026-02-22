from fastapi import APIRouter, Depends
from requests import Session
from Models.utils.tokenmanage import token
from Models.Classes.token_authentication import decode_token
from Models import Classes
from Models.db import schemas
from Models.db import get_db
from Models.utils.utils import util
from Models.utils.config import settings

router = APIRouter(prefix="/v1/HR/bgv", tags=["HR"])

@router.get("/get-info/")
async def getbgvinfo(
    Company_portal_Url: str,
    uuid: str,
    token_info: dict = Depends(decode_token),
    db: Session = Depends(get_db)
):
    cp = Company_portal_Url
    uid = token_info["Id"]
    util.is_admin(token_info)
    
    tk = token(db, cp)
    us = Classes.GetUser(db, cp)
    bg = Classes.UserBGVManager(db, cp)
    
    tk.checktoken(uid)
    if us.get_userdetails_by_uuid(uuid):
        result = bg.get_user_bgv(uuid)
        return result
    
@router.put("/update-info/")
async def update_bgv_info(
    Company_portal_Url: str,
    data: schemas.BritsUserBGVUpdateSchema,
    uuid: str,
    token_info: dict = Depends(decode_token),
    db: Session = Depends(get_db)
):
    cp = Company_portal_Url
    uid = token_info["Id"]
    util.is_admin(token_info)
    
    tk = token(db, cp)
    us = Classes.GetUser(db, cp)
    bg = Classes.UserBGVManager(db, cp)
    
    tk.checktoken(uid)
    if us.get_userdetails_by_uuid(uuid):
    
        rdata = bg.prepare_update_data(data)
        bg.update_bgv_data(rdata, uuid)
        bg.update_verification_results(data, uuid)
        bg.insert_bgv_master(uuid)
        return util.success("bgv-updated")
        
    else:
        return util.error_message("error occured")