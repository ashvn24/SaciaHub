from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from requests import Session
from Models.utils.tokenmanage import token
from Models.Classes.token_authentication import decode_token
from Models import Classes
from Models.db import schemas
from Models.db import get_db
from Models.utils.utils import util

router = APIRouter(prefix="/v1/admin/violation", tags=["Admin/Violation"])


@router.post("/report/", operation_id="violation-report")
async def report_user(
    data: schemas.violationSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db)
):
    cp = data.Company_Portal_Url
    uuid = data.Useruuid
    tid = token_info["Id"]
    
    tk = token(db, cp)
    vl = Classes.violation(db, cp)
    user = Classes.GetUser(db, cp)
    bgv = Classes.UserBGVManager(db, cp)
    uinfo = Classes.authmanager(db, cp)
    
    tk.checktoken(tid)
    util.is_admin(token_info)
    
    result = user.get_userdetails_by_uuid(uuid)
    if result:
        ins = vl.add_violation(data)
        params = {"status": "Rejected"}
        modules = ["Applications"]
        bgv.update_bgv_data(params, uuid)
        uinfo.update_modules(uuid, modules)
    if ins:
        return JSONResponse(status_code=200, content={"message": "violation reported"})
    
@router.get("/get-report/", operation_id="get-violation")
async def get_violation(
    Company_Portal_Url: str,
    useruuid: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db)
):
    cp = Company_Portal_Url
    tid = token_info["Id"]
    
    tk = token(db, cp)
    vl = Classes.violation(db, cp)
    user = Classes.GetUser(db, cp)
    
    tk.checktoken(tid)
    util.is_admin(token_info)
    
    result = user.get_userdetails_by_uuid(useruuid)
    if not result: util.error_message("user not found")
    vdata = vl.get_violation(useruuid)
    
    if not vdata:
        util.error_message("Error occured")
    res = util.success("violation results")
    res["content"] = vdata
    return res