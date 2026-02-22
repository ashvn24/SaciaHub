"""
User management endpoints.
Preserves all original route paths under /v1/user.
"""

import base64
import calendar
import io
import json
import os
from datetime import timedelta, datetime
from typing import Dict, List, Optional

from dateutil.relativedelta import relativedelta
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
import requests as http_requests
from msal import ConfidentialClientApplication
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.core.security import create_access_token
from src.dependencies.auth import get_current_user
from src.models.database import get_db
from src.repositories.token import TokenRepository
from src.schemas.auth import ForgotPassword, UpdatePassword, otpSchema, resendSchema, SignInSchema
from src.schemas.bgv import BritsUserBGVSchema, BritsUserBGVUpdateSchema
from src.schemas.notification import UpdateNotification
from src.schemas.request import DeleteRequest, RequestSchema, UpdateRequestSchema
from src.schemas.timesheet import (
    DeleteTimeSheet,
    TimesheetCountResponse,
    TimesheetSchema,
    UpdateTimeSheet,
)

logger = get_logger("api.user")

SCOPES = ["User.Read", "GroupMember.Read.All"]
ACCESS_TOKEN_EXPIRE_MINUTES = 60

user_router = APIRouter(prefix="/v1/user", tags=["User"])


def _check_token(db: Session, portal_url: str, user_id: str) -> None:
    TokenRepository(db, portal_url).check_token(user_id)


# ──────────────────────── Authentication ────────────────────────

@user_router.post("/signin/")
async def signin_route(
    request: Request,
    response: Response,
    data: SignInSchema,
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    result = await auth_manager.signin(request, response, data)

    if "message" in result and result["message"] == "2FA verification required":
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)

    headers = {
        "Authorization": f"Bearer {result['access_token']}",
        "Refresh-Token": result["refresh_token"],
    }
    del result["access_token"]
    del result["refresh_token"]
    return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


@user_router.post("/sso_auth/")
def sso_login(
    email: str = Form(""),
    Company_Portal_Url: str = Form(""),
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager
    from src.core.exceptions import BadRequestException

    udata = UserAuthManager(db, Company_Portal_Url)
    user_info = udata._get_user(email)
    if user_info:
        response = udata.get_msal_connetion(user_info.TenantUUID)
        if not response["sucess"]:
            return JSONResponse(content=response, status_code=response["status_code"])
        result, AUTHORITY = response["result"], response["AUTHORITY"]
        payload = {"vendor_id": str(user_info.TenantUUID)}
        msal_app = ConfidentialClientApplication(
            result.ms_client_id,
            authority=AUTHORITY,
            client_credential=result.ms_client_secret,
        )
        state = json.dumps(payload)
        auth_url = msal_app.get_authorization_request_url(SCOPES, state=state)
        return JSONResponse(content={"auth_url": auth_url, "status_code": 200}, status_code=200)
    else:
        raise BadRequestException("User don't have account with SaciaHub")


@user_router.get("/getAToken")
def authorized(
    request: Request,
    Company_Portal_Url: str,
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    auth = UserAuthManager(db, Company_Portal_Url)
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        raise BadRequestException("No code found")
    if state:
        payload = json.loads(state)
        vendor_id = payload.get("vendor_id")
    else:
        return "state is not present"

    response = auth.get_msal_connetion(vendor_id)
    if not response["sucess"]:
        return JSONResponse(content=response, status_code=response["status_code"])
    result, AUTHORITY = response["result"], response["AUTHORITY"]
    msal_app = ConfidentialClientApplication(
        result.ms_client_id,
        authority=AUTHORITY,
        client_credential=result.ms_client_secret,
    )
    result = msal_app.acquire_token_by_authorization_code(code, scopes=SCOPES)
    if "access_token" in result:
        if result["id_token_claims"]["roles"] in ["", [], None]:
            res = {"auth": {"success": False, "message": "Your Account is not Added in SSO Group, Contact your Admin to Add"}}
            return JSONResponse(content=res, status_code=401)
        content = {
            "username": result["id_token_claims"]["preferred_username"],
            "role": result["id_token_claims"]["roles"][0],
        }
        userdata = auth._get_user(content["username"])
        result = auth._create_response(userdata)
        if "message" in result and result["message"] == "2FA verification required":
            return JSONResponse(content=result, status_code=status.HTTP_200_OK)
        headers = {
            "Authorization": f"Bearer {result['access_token']}",
            "Refresh-Token": result["refresh_token"],
        }
        del result["access_token"]
        del result["refresh_token"]
        return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


@user_router.get("/verify-2fa/")
async def verify_2fa_route(
    token: str,
    email: str,
    Company_Portal_Url: str,
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    auth_manager = UserAuthManager(db, Company_Portal_Url)
    is_verified = await auth_manager.await_2fa_verification(token, email, timeout=120)

    if not is_verified:
        raise UnauthorizedException("2FA verification failed or timed out")

    data = {"username": email}
    user = auth_manager._get_user(email)
    result = await auth_manager._create_response(user, data)

    headers = {
        "Authorization": f"Bearer {result['access_token']}",
        "Refresh-Token": result["refresh_token"],
    }
    del result["access_token"]
    del result["refresh_token"]
    return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


@user_router.post("/signout/")
async def signout_route(
    Company_Portal_Url: str,
    token: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    auth_manager = UserAuthManager(db, Company_Portal_Url)
    return auth_manager.signout(token)


@user_router.post("/refresh/")
async def refresh_access_token(token_info: Dict = Depends(get_current_user)):
    from Models.Classes.UserManager import UserAuthManager

    auth_manager = UserAuthManager(db=None, Company_portal_Url=None)
    result = auth_manager.refresh_token(token_info)

    headers = {"Authorization": f"Bearer {result['access_token']}"}
    del result["access_token"]
    return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


# ──────────────────────── Profile ────────────────────────

@user_router.patch("/update-profile/{path_suffix:path}")
async def update_profile(
    Company_Portal_Url: str,
    data: Optional[str] = None,
    path_suffix: str = "",
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    auth_manager = UserAuthManager(db, Company_Portal_Url)
    return auth_manager.update_profile(data, path_suffix, token_info)


@user_router.post("/forgot-password/")
async def forgot_password(data: ForgotPassword, db: Session = Depends(get_db)):
    from Models.Classes.UserManager import UserAuthManager

    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    return auth_manager.forgot_password(data)


@user_router.post("/verify-otp/")
async def verify_otp(data: otpSchema, db: Session = Depends(get_db)):
    from Models.Classes.UserManager import UserAuthManager
    from src.core.exceptions import BadRequestException

    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    if auth_manager.verify_otp(data.token, data.email):
        token = create_access_token({"user": data.email}, expires_delta=timedelta(minutes=2))
        headers = {"Authorization": token}
        return JSONResponse(
            content={"message": "verified"},
            status_code=status.HTTP_200_OK,
            headers=headers,
        )
    else:
        raise BadRequestException("invalid otp")


@user_router.post("/resend/{mail}")
async def resend_mail(
    data: resendSchema,
    mail: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    return auth_manager.resend_mail_or_otp(data, mail)


@user_router.patch("/update-password/")
async def update_password(
    data: UpdatePassword,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.UserManager import UserAuthManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    return auth_manager.update_password(data, token_info)


# ──────────────────────── BGV ────────────────────────

@user_router.post("/userbgv/", operation_id="create_user_bgv")
async def user_bgv_route(
    data: BritsUserBGVSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    bgv_manager = UserBGVManager(db, data.Company_Portal_Url, logger)
    return bgv_manager.create_user_bgv(data, token_info)


@user_router.put("/userbgv/", operation_id="update_user_bgv")
async def update_user_bgv_route(
    Company_Portal_Url: str,
    data: BritsUserBGVUpdateSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    bgv_manager = UserBGVManager(db, Company_Portal_Url, logger)
    return await bgv_manager.update_user_bgv(data, token_info)


@user_router.get("/digilocker/callback", operation_id="digilocker_callback")
async def digilocker_callback(request: Request):
    auth_code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not auth_code:
        return {"error": "Authorization code not found in callback"}
    logger.info(f"Received DigiLocker auth_code={auth_code}, state={state}")
    return {"auth_code": auth_code, "state": state, "message": "Callback received successfully"}


@user_router.get("/adhar_link/", operation_id="adhar_link")
async def adhar_link_route(
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    bgv_manager = UserBGVManager(db, Company_Portal_Url, logger)
    result = await bgv_manager.get_adhar_link()
    return json.loads(result)


@user_router.get("/userbgv/", operation_id="get_user_bgv")
async def get_user_bgv_route(
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager
    from Models.Classes.violation import violation

    _check_token(db, Company_Portal_Url, token_info["Id"])
    bgv_manager = UserBGVManager(db, Company_Portal_Url, logger)
    bgvdata = bgv_manager.get_user_bgv_data(token_info)
    vinfo = violation(db, Company_Portal_Url)
    vdata = vinfo.get_violation(token_info["Id"])
    if vdata:
        bgvdata["violations"] = vdata
    return bgvdata


# ──────────────────────── Media ────────────────────────

@user_router.post("/uploadMedia/")
async def upload_route(
    Company_Portal_Url: str,
    extract: int,
    files: List[UploadFile] = File(...),
    user: Optional[str] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.MediaManager import MediaManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    media_manager = MediaManager(db, token_info, Company_Portal_Url)
    result = await media_manager.upload_media(files, user, extract)
    return JSONResponse(status_code=201, content=result)


@user_router.get("/getMedia/")
async def get_files_route(
    Company_Portal_Url: str,
    file: str,
    user: Optional[str] = None,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.MediaManager import MediaManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    media_manager = MediaManager(db, token_info, Company_Portal_Url)
    result = await media_manager.get_media(file, user)
    file_extension = os.path.splitext(file)[1].lstrip(".")
    if file_extension not in ["jpg", "jpeg", "png", "gif", "webp"]:
        return JSONResponse(status_code=200, content=result)
    try:
        response = http_requests.get(result, timeout=10)
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get("Content-Type", "image/jpeg")
        base64_content = base64.b64encode(content).decode("utf-8")
        return Response(
            content=base64_content,
            media_type=content_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception as e:
        raise e


# ──────────────────────── Timesheets ────────────────────────

@user_router.post("/timeSheets/", operation_id="create_time_sheet")
async def create_time_sheet(
    request: Request,
    data: TimesheetSchema,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimesheetManager import CreateTimeSheetManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    time_sheet_manager = CreateTimeSheetManager(db, token_info, data.Company_Portal_Url)
    return await time_sheet_manager.create_time_sheet(data, request)


@user_router.get("/timeSheets/")
async def get_time_sheets(
    request: Request,
    response: Response,
    Company_Portal_Url: str,
    user_ids: str = Query(None),
    Day: Optional[str] = None,
    Week: Optional[str] = None,
    Month: Optional[str] = None,
    param: Optional[str] = None,
    pagenum: Optional[int] = None,
    own: Optional[int] = None,
    token_info: Dict = Depends(get_current_user),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
    db: Session = Depends(get_db),
    filterBy: Optional[str] = Query(None),
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.TimesheetManager import ViewTimeSheetManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    time_sheet_manager = ViewTimeSheetManager(db, Company_Portal_Url, token_info)
    if user_ids:
        user_ids_list = [int(id) for id in user_ids.split(",")]
        user_uuid_fetcher = GetUser(db, Company_Portal_Url)
        user_uuids = user_uuid_fetcher.get_user_uuids(user_ids_list)
        return time_sheet_manager.get_time_sheets(
            Day, Week, Month, user_uuids, pagenum=pagenum, sortBy=sortBy, order=order, filterBy=filterBy
        )
    return time_sheet_manager.get_time_sheets(
        Day, Week, Month, param=param, pagenum=pagenum, own=own, sortBy=sortBy, order=order, filterBy=filterBy
    )


@user_router.put("/timeSheets/", operation_id="update_time_sheet")
async def update_time_sheet(
    data: UpdateTimeSheet,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimesheetManager import CreateTimeSheetManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    time_sheet_manager = CreateTimeSheetManager(db, token_info, data.Company_Portal_Url)
    return time_sheet_manager.update_time_sheet(data)


@user_router.delete("/timeSheets/", operation_id="delete_time_sheets")
async def delete_time_sheets(
    data: DeleteTimeSheet,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimesheetManager import CreateTimeSheetManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    time_sheet_manager = CreateTimeSheetManager(db, token_info, data.Company_Portal_Url)
    return time_sheet_manager.delete_time_sheets(data)


@user_router.get("/timeSheets/count/", response_model=List[TimesheetCountResponse])
async def get_timesheet_counts(
    Company_Portal_Url: str,
    year: int = None,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.Dashboard import TimesheetCountService

    _check_token(db, Company_Portal_Url, token_info["Id"])
    service = TimesheetCountService(db, token_info, Company_Portal_Url)
    return service.get_timesheet_counts(year)


# ──────────────────────── Requests ────────────────────────

@user_router.post("/request/", operation_id="request-create")
async def create_request(
    data: RequestSchema,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.RequestManager import RequestManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    request_manager = RequestManager(db, token_info)
    return await request_manager.create_request(data)


@user_router.get("/request/{path_suffix:path}", operation_id="request-get")
async def get_requests(
    Company_Portal_Url: str,
    Type: Optional[str] = None,
    user_ids: Optional[str] = None,
    path_suffix: str = "",
    pagenum: Optional[int] = None,
    own: Optional[int] = None,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
    Status: Optional[str] = None,
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.RequestManager import RequestManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    request_manager = RequestManager(db, token_info)
    if user_ids:
        user_ids_list = [int(id) for id in user_ids.split(",")]
        user_uuid_fetcher = GetUser(db, Company_Portal_Url)
        user_uuids = user_uuid_fetcher.get_user_uuids(user_ids_list)
        return request_manager.get_requests(
            Company_Portal_Url, Type, user_uuids, pagenum=pagenum, own=own, sortBy=sortBy, order=order, Status=Status
        )
    return request_manager.get_requests(
        Company_Portal_Url, Type, path_suffix=path_suffix, pagenum=pagenum, own=own, sortBy=sortBy, order=order, Status=Status
    )


@user_router.put("/request/", operation_id="request-update")
async def update_request_route(
    data: UpdateRequestSchema,
    ID: int,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.RequestManager import RequestManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    request_manager = RequestManager(db, token_info)
    return request_manager.update_request(data, id=ID)


@user_router.delete("/request/", operation_id="request-delete")
async def delete_request_route(
    data: DeleteRequest,
    token_info: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.RequestManager import RequestManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    request_manager = RequestManager(db, token_info)
    return await request_manager.delete_request(data)


@user_router.get("/request_counts/", operation_id="get_request_counts")
async def get_request_counts(
    Company_Portal_Url: str,
    Day: Optional[str] = None,
    Week: Optional[str] = None,
    Month: Optional[str] = None,
    Type: Optional[str] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.Dashboard import RequestCountsService

    _check_token(db, Company_Portal_Url, token_info["Id"])
    service = RequestCountsService(db, token_info, Company_Portal_Url)
    return service.get_request_counts(Day, Week, Month, Type)


# ──────────────────────── Notifications ────────────────────────

@user_router.get("/notification/")
async def get_notification(
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.customerVerifier import CustomerUserVerifier
    from Models.Classes.Notification import ManageNotification

    _check_token(db, Company_Portal_Url, token_info["Id"])
    cust = CustomerUserVerifier(db)
    customer = cust._get_customer(Company_Portal_Url)
    notification = ManageNotification(db, customer)
    return await notification.get_notification(token_info)


@user_router.put("/notification/")
async def update_notification(
    Company_Portal_Url: str,
    payload: UpdateNotification,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.customerVerifier import CustomerUserVerifier
    from Models.Classes.Notification import ManageNotification

    _check_token(db, Company_Portal_Url, token_info["Id"])
    cust = CustomerUserVerifier(db)
    customer = cust._get_customer(Company_Portal_Url)
    notification = ManageNotification(db, customer)
    await notification.update_notification(payload.notification_ids, payload.read)
    suffix = "s" if len(payload.notification_ids) > 1 else ""
    return {"status": "success", "message": f"Notification{suffix} updated successfully."}


# ──────────────────────── Holiday ────────────────────────

@user_router.get("/getUserHoliday/")
async def get_holiday_user(
    Company_Portal_Url: str,
    ID: Optional[str] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, Company_Portal_Url, token_info["Id"])
    return await ManageHolidayPolicy(db, token_info).getUserHoliday(Company_Portal_Url)


@user_router.post("/reportbgv/")
def create_bgv_report(
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.userbgvManager import UserBGVManager

    UserBGVManager(db).create_bgv_report(token_info["Id"], Company_Portal_Url)
    _check_token(db, Company_Portal_Url, token_info["Id"])


# ──────────────────────── Remaining Hours ────────────────────────

@user_router.get("/remaining-hours/")
async def get_rem_hours(
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy
    from Models.Classes.RequestManager import RequestManager
    from Models.Classes.TimesheetManager import ViewTimeSheetManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    own = 1

    request_manager = RequestManager(db, token_info)
    holiday = ManageHolidayPolicy(db, token_info)
    tim = ViewTimeSheetManager(db, Company_Portal_Url, token_info)

    current_date = datetime.now()
    start_date = (current_date - relativedelta(months=2)).replace(day=1)
    end_date = current_date.replace(
        day=calendar.monthrange(current_date.year, current_date.month)[1]
    )

    months_to_fetch = []
    temp_date = start_date
    while temp_date <= end_date:
        months_to_fetch.append(temp_date.strftime("%Y-%m"))
        temp_date += relativedelta(months=1)

    req_data = request_manager.get_requests(
        Company_Portal_Url, request_type="TimeOff", path_suffix="REQTOF", own=own
    )
    if not isinstance(req_data, list):
        req_data = [req_data] if isinstance(req_data, dict) else []

    processed_req_data = [
        {
            "REQN": req.get("REQN", ""),
            "RequestDetails": req.get("RequestDetails", {}),
            "RequestStatus": req.get("RequestStatus", ""),
        }
        for req in req_data
    ]

    reqtm_data = [
        {
            "REQN": req.get("REQN", ""),
            "RequestDetails": req.get("RequestDetails", {}),
            "RequestStatus": req.get("RequestStatus", ""),
        }
        for req in request_manager.get_requests(
            Company_Portal_Url, request_type="TimeSheet", path_suffix="REQTIM", own=own
        )
    ]

    h_data = await holiday.getUserHoliday(Company_Portal_Url)

    timesheet_data = []
    for month in months_to_fetch:
        month_data = tim.get_time_sheets(day=month, own=own)
        timesheet_data.extend(month_data if isinstance(month_data, list) else [month_data])

    return {
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "months_included": months_to_fetch,
        },
        "time_off_requests": processed_req_data,
        "missed_timesheet": reqtm_data,
        "holiday_policy": h_data,
        "timesheets": timesheet_data,
    }
