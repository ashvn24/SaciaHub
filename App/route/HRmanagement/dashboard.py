import logging
from fastapi import APIRouter
from App.Models.Classes.Dashboard import get_hr_dashboard
from App.Models.Classes.token_authentication import decode_token
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from Models.db import get_db
from Models.utils.tokenmanage import token


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/HR", tags=["HR"])

@router.get("/Dashboard/")
async def get_dashboard_data(
    Company_portal_Url: str,
    token_info: dict = Depends(decode_token),
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    cp = Company_portal_Url
    uid = token_info["Id"]
    
    tk = token(db, cp)
    tk.checktoken(uid)
    manager_dashboard = get_hr_dashboard(db, cp, token_info, type)
    return manager_dashboard