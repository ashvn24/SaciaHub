from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from requests import Session
from App.Models.Classes.Dashboard import AdminDashboard
from Models.utils.tokenmanage import token
from Models.utils.utils import util
from App.Models.Classes.token_authentication import decode_token
from Models import Classes
from Models.db import schemas
from Models.db import get_db

router = APIRouter(prefix="/v1/admin", tags=["Admin"])

@router.post('/dashboard/', operation_id="admin-dashboard")
def admindash(
    Company_portal_Url: str,
    token_info: dict = Depends(decode_token),
    db: Session = Depends(get_db)
):
    cp = Company_portal_Url
    uid = token_info["Id"]
    
    tk = token(db, cp)
    tk.checktoken(uid)
    dashb = AdminDashboard(db, cp, token_info)
    return dashb.admindashboard()
    
    