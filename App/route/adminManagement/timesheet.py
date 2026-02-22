from fastapi import APIRouter, Depends, HTTPException, Request, logger, status
from fastapi.responses import JSONResponse
from requests import Session
from Models.utils.tokenmanage import token
from Models.Classes.token_authentication import decode_token
from Models import Classes
from Models.db import schemas
from Models.db import get_db
import sys
from Models.utils.error_handler import ErrorHandler
import logging

logger = logging.getLogger(__name__)
error = ErrorHandler()

router = APIRouter(prefix="/v1/admin", tags=["Admin/timesheet"])

@router.post("/TimesheetReport/", operation_id="timesheet-report")
async def admin_timesheet_route(
    request: Request,
    data: schemas.AdminTimesheet,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    report_manager = Classes.TimesheetReportManager(db, request)
    return await report_manager.admin_timesheet(data, token_info)


# The above code snippet is creating an empty list named `week_ranges`.
@router.put("/TimesheetStatus/", operation_id="timesheet-status")
async def approve_timesheet(
    data: schemas.UpdateTimesheet,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        cp = data.Company_Portal_Url
        uid = token_info["Id"]
        tk = token(db, cp)
        verifier = Classes.CustomerUserVerifier(db)
        tm = Classes.TimesheetManagerStatus(db)
        
        tk.checktoken(uid)
        result = verifier.verify_customer_and_user(cp, uid)
        if isinstance(result, JSONResponse): return result 
        customer, user = result

        return await tm.approve_timesheet(data, token_info, customer)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"An unexpected error occurred at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e