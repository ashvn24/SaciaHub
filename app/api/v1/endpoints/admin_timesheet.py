"""
Admin timesheet endpoints.
Preserves all original route paths under /v1/admin.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.dependencies.auth import get_current_user
from app.models.database import get_db
from app.repositories.token import TokenRepository
from app.schemas.timesheet import AdminTimesheet, UpdateTimesheet

logger = get_logger("api.admin_timesheet")

admin_timesheet_router = APIRouter(prefix="/v1/admin", tags=["Admin/timesheet"])


def _check_token(db: Session, portal_url: str, user_id: str) -> None:
    TokenRepository(db, portal_url).check_token(user_id)


@admin_timesheet_router.post("/TimesheetReport/", operation_id="timesheet-report")
async def admin_timesheet_route(
    request: Request,
    data: AdminTimesheet,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.Report import TimesheetReportManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    report_manager = TimesheetReportManager(db, request)
    return await report_manager.admin_timesheet(data, token_info)


@admin_timesheet_router.put("/TimesheetStatus/", operation_id="timesheet-status")
async def approve_timesheet(
    data: UpdateTimesheet,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.customerVerifier import CustomerUserVerifier
    from Models.Classes.TimesheetManager import TimesheetManagerStatus

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    verifier = CustomerUserVerifier(db)
    result = verifier.verify_customer_and_user(data.Company_Portal_Url, token_info["Id"])
    if isinstance(result, JSONResponse):
        return result
    customer, user = result

    tm = TimesheetManagerStatus(db)
    return await tm.approve_timesheet(data, token_info, customer)
