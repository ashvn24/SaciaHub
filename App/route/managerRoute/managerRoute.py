import logging
from fastapi import APIRouter
from App.Models.Classes.Dashboard import ManagerDashboardExtension, get_manager_dashboard
from App.Models.Classes.token_authentication import decode_token
from Models.db.db_connection import SessionLocal
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

logger = logging.getLogger(__name__)


manager_router = APIRouter(prefix="/v1/manager", tags=["Manager"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
@manager_router.get("/Dashboard/")
async def get_dashboard_data(
    Company_portal_Url: str,
    token_info: dict = Depends(decode_token),
    db: Session = Depends(get_db)
):
    manager_dashboard = ManagerDashboardExtension(db, Company_portal_Url, token_info)
    return manager_dashboard.get_manager_dashboard_data()

