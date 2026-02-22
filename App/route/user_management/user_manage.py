import base64
import calendar
from datetime import timedelta, datetime
import io
import json
import logging
import os
import time
from functools import wraps
from typing import Dict, List, Optional
from dateutil.relativedelta import relativedelta
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
    Body,
)
from fastapi.responses import JSONResponse, StreamingResponse
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from Models.Classes.violation import violation
from Models.utils.tokenmanage import token
from Models.Classes.HolidayPolicy import ManageHolidayPolicy
from Models.Classes.Dashboard import RequestCountsService, TimesheetCountService
from Models.Classes.UserManager import UserAuthManager
from Models.Classes.MediaManager import MediaManager
from Models.Classes.userbgvManager import UserBGVManager
from Models.Classes.logger import APILogger
from Models.Classes.customerVerifier import CustomerUserVerifier
from Models.Classes.Notification import ManageNotification
from Models.Classes.RequestManager import RequestManager
from Models.Classes.GetUser import GetUser
from Models.Classes.TimesheetManager import CreateTimeSheetManager, ViewTimeSheetManager
from Models.db.schemas import (
    BritsUserBGVSchema,
    BritsUserBGVUpdateSchema,
    DeleteRequest,
    DeleteTimeSheet,
    ForgotPassword,
    RequestSchema,
    SignInSchema,
    TimesheetCountResponse,
    TimesheetSchema,
    UpdatePassword,
    UpdateRequestSchema,
    UpdateTimeSheet,
    otpSchema,
    resendSchema,
    UpdateNotification,
)
from Models.db.db_connection import SessionLocal, engine
from Models.Classes.token_authentication import create_access_token, decode_token
from dotenv import load_dotenv
from msal import ConfidentialClientApplication
from typing import Union, List
import sys
import json
from Models.utils.error_handler import ErrorHandler


error = ErrorHandler()

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = ['User.Read', 'GroupMember.Read.All']

ACCESS_TOKEN_EXPIRE_MINUTES = 60

user_router = APIRouter(prefix="/v1/user", tags=["User"])

db = SessionLocal(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_api_call(db_func):
    @wraps(db_func)
    async def wrapper(request: Request, response: Response, *args, **kwargs):
        start_time = time.time()
        db = kwargs.get('db')
        company_portal_url = kwargs.get('Company_Portal_Url') or kwargs.get('data', {}).get('Company_Portal_Url')
        api_logger = APILogger(db, company_portal_url)

        try:
            result = await db_func(request, *args, **kwargs)
            execution_time = time.time() - start_time

            user_uuid = getattr(result, 'UserUUID', None)
            if user_uuid is None and isinstance(result, dict):
                user_uuid = result.get('UserUUID')
            if user_uuid is None:
                user_uuid = kwargs.get('token_info', {}).get('Id')

            response = result if isinstance(result, Response) else Response(content=result)
            await api_logger.log_api_call(request, response, user_uuid, execution_time)
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            await api_logger.log_api_call(request, None, None, execution_time)
            raise e

    return wrapper

@user_router.post("/signin/")
async def signin_route(request: Request, response: Response, data: SignInSchema, db: Session = Depends(get_db)):
    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    result = await auth_manager.signin(request, response, data)

    # print("\n----------------Result Of Signin----------------:", result)

    if "message" in result and result["message"] == "2FA verification required":
        print("\n----------------Result Of 2FA----------------:", result)
        return JSONResponse(content=result, status_code=status.HTTP_200_OK)
    else:
        headers = {
            "Authorization": f"Bearer {result['access_token']}",
            "Refresh-Token": result['refresh_token'],
        }
        del result['access_token']
        del result['refresh_token']
        return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)
    
@user_router.post('/sso_auth/')
def login(email: str = Form(""), Company_Portal_Url: str = Form(""), db: Session = Depends(get_db)):
    try:
        udata = UserAuthManager(db, Company_Portal_Url)
        user_info = udata._get_user(email)
        if user_info:
            response = udata.get_msal_connetion(user_info.TenantUUID)
            if not response["sucess"]:
                return JSONResponse(content=response, status_code=response["status_code"])
            result, AUTHORITY = response["result"], response["AUTHORITY"]
            payload = {"vendor_id" : str(user_info.TenantUUID)}
            msal_app = ConfidentialClientApplication(
                result.ms_client_id, authority=AUTHORITY,
                client_credential=result.ms_client_secret
            )
            SCOPES = ['User.Read', 'GroupMember.Read.All']
            state = json.dumps(payload)
            auth_url = msal_app.get_authorization_request_url(SCOPES, state=state)
            response_contect = {"auth_url": auth_url, "status_code": 200}
            return JSONResponse(content=response_contect, status_code=200)
        else:
            return error.error("User don't have account with SaciaHub", 400, "User don't have account with SaciaHub")
    except Exception as e:
        raise e
    
@user_router.get('/getAToken')
def authorized(request: Request, Company_Portal_Url: str, db: Session = Depends(get_db)):
    auth = UserAuthManager(db, Company_Portal_Url)
    code = request.query_params.get('code')
    state = request.query_params.get('state')
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No code found")
    if state:
        payload = json.loads(state)  # Decode the state parameter to get the payload
        vendor_id = payload.get('vendor_id')
    else:
        return "state is not present"
    response = auth.get_msal_connetion(vendor_id)
    if not response["sucess"]:
        return JSONResponse(content=response, status_code=response["status_code"])
    result, AUTHORITY = response["result"], response["AUTHORITY"]
    msal_app = ConfidentialClientApplication(
        result.ms_client_id, authority=AUTHORITY,
        client_credential=result.ms_client_secret
    )
    result = msal_app.acquire_token_by_authorization_code(
        code, scopes=SCOPES)
    if 'access_token' in result:
        if result["id_token_claims"]["roles"] in ["", [], None]:
            res = {"auth": {"success": False, "message": "Your Account is not Added in SSO Group, Contact your Admin to Add"}}
            return JSONResponse(content=res, status_code=401)
        content={
            "username": result["id_token_claims"]["preferred_username"],
            "role": result["id_token_claims"]["roles"][0]
        }
        userdata = auth._get_user(content["username"])
        result = auth._create_response(userdata)
        if "message" in result and result["message"] == "2FA verification required":
            return JSONResponse(content=result, status_code=status.HTTP_200_OK)
        else:
            headers = {
                "Authorization": f"Bearer {result['access_token']}",
                "Refresh-Token": result['refresh_token'],
            }
            del result['access_token']
            del result['refresh_token']
            return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


@user_router.get("/verify-2fa/")
async def verify_2fa_route(token: str, email: str, Company_Portal_Url: str, db: Session = Depends(get_db)):
    auth_manager = UserAuthManager(db, Company_Portal_Url)
    is_verified = await auth_manager.await_2fa_verification(token, email, timeout=120)

    if not is_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="2FA verification failed or timed out")

    data = {"username": email}
    user = auth_manager._get_user(email)
    result = await auth_manager._create_response(user, data)

    headers = {
        "Authorization": f"Bearer {result['access_token']}",
        "Refresh-Token": result['refresh_token'],
    }
    del result['access_token']
    del result['refresh_token']
    return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


@user_router.post("/signout/")
async def signout_route(Company_Portal_Url: str, token: str = Depends(decode_token), db:Session = Depends(get_db)):
    auth_manager = UserAuthManager(db, Company_Portal_Url)
    return auth_manager.signout(token)


@user_router.post("/refresh/")
async def refresh_access_token(token_info: Dict = Depends(decode_token)):
    auth_manager = UserAuthManager(db=None, Company_portal_Url=None)
    result = auth_manager.refresh_token(token_info)

    headers = {"Authorization": f"Bearer {result['access_token']}"}
    del result['access_token']
    return JSONResponse(content=result, status_code=status.HTTP_200_OK, headers=headers)


@user_router.patch("/update-profile/{path_suffix:path}")
async def update_profile(
    Company_Portal_Url: str,
    data: Optional[str] = None,
    path_suffix: str = "",
    token_info: Dict = Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        auth_manager = UserAuthManager(db, Company_Portal_Url)
        return auth_manager.update_profile(data, path_suffix, token_info)
    except Exception as e:
        logger.error(f"Error in update_profile: {e}")
        raise e


@user_router.post("/forgot-password/")
async def forgot_password(data: ForgotPassword, db: Session = Depends(get_db)):
    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    return auth_manager.forgot_password(data)

@user_router.post("/verify-otp/")
async def verify_otp(data:otpSchema, db: Session = Depends(get_db)):
    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    if auth_manager.verify_otp(data.token, data.email):
        token = create_access_token({"user":data.email},expires_delta=  timedelta(minutes=2))
        headers = {
            "Authorization": token
        }
        return JSONResponse(content={"message":"verified"}, status_code=status.HTTP_200_OK, headers=headers)
    else:
        return error.error("invalid otp", 400, "Invalid OTP")
    
@user_router.post("/resend/{mail}")
async def resend_mail(data: resendSchema, mail: Optional[str] =None, db:Session = Depends(get_db)):
    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    return auth_manager.resend_mail_or_otp(data, mail)


@user_router.patch("/update-password/")
async def update_password(data: UpdatePassword, token_info: Dict = Depends(decode_token), db: Session = Depends(get_db)):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    auth_manager = UserAuthManager(db, data.Company_Portal_Url)
    return auth_manager.update_password(data, token_info)


@user_router.post("/userbgv/", operation_id="create_user_bgv")
async def user_bgv_route(data: BritsUserBGVSchema, token_info=Depends(decode_token), db: Session = Depends(get_db)):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    bgv_manager = UserBGVManager(db, data.Company_Portal_Url, logger)
    return bgv_manager.create_user_bgv(data, token_info)



@user_router.put("/userbgv/", operation_id="update_user_bgv")
async def update_user_bgv_route(
    Company_Portal_Url: str,
    data: BritsUserBGVUpdateSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    bgv_manager = UserBGVManager(db, Company_Portal_Url, logger)
    result =  await bgv_manager.update_user_bgv(data, token_info)
    return result

@user_router.get("/digilocker/callback", operation_id="digilocker_callback")
async def digilocker_callback(request: Request):
    """
    Handles DigiLocker OAuth2 redirect and extracts authorization code + state.
    DigiLocker will redirect here with ?code=xxx&state=yyy
    """
    auth_code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not auth_code:
        return {"error": "Authorization code not found in callback"}
    # You can now exchange this code for an access token with DigiLocker
    # Example: call your manager function to handle token exchange

    logger.info(f"Received DigiLocker auth_code={auth_code}, state={state}")
    return {"auth_code": auth_code, "state": state, "message": "Callback received successfully"}

@user_router.get("/adhar_link/", operation_id="adhar_link")
async def adhar_link_route(
    Company_Portal_Url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    bgv_manager = UserBGVManager(db, Company_Portal_Url, logger)
    result =  await bgv_manager.get_adhar_link()
    print("Result:", result)
    return json.loads(result)


@user_router.get("/userbgv/", operation_id="get_user_bgv")
async def get_user_bgv_route(Company_Portal_Url: str, token_info=Depends(decode_token), db: Session = Depends(get_db)):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    bgv_manager = UserBGVManager(db, Company_Portal_Url, logger)
    bgvdata = bgv_manager.get_user_bgv_data(token_info)
    vinfo = violation(db, Company_Portal_Url)
    vdata = vinfo.get_violation(token_info["Id"])
    if vdata:
        bgvdata["violations"] = vdata
    return bgvdata


@user_router.post("/uploadMedia/")
async def upload_route(
    Company_Portal_Url: str,
    extract: int,
    files: List[UploadFile] = File(...),
    user: Optional[str] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    media_manager = MediaManager(db, token_info, Company_Portal_Url)
    result = await media_manager.upload_media(files, user, extract)
    return JSONResponse(status_code=201, content=result)


@user_router.get("/getMedia/")
async def get_files_route(
    Company_Portal_Url: str,
    file: str,
    user: Optional[str] = None,
    token_info: Dict = Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    media_manager = MediaManager(db, token_info, Company_Portal_Url)
    result = await media_manager.get_media(file, user)
    file_extension = os.path.splitext(file)[1].lstrip('.')
    if file_extension not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        return JSONResponse(
        status_code=200,
        content=result
    )
    try:
        response = requests.get(result, timeout=10)
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        base64_content = base64.b64encode(content).decode("utf-8")
        return Response(
                content=base64_content,
                media_type=content_type,
                headers={
                    "Access-Control-Allow-Origin": "*"
                }
            )
        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Content-Disposition": f'inline; filename="{os.path.basename(file)}"'
            }
        )
    except Exception as e:
        raise e
        
# @user_router.get("/getMedia/")
# async def get_files_route(
#     Company_Portal_Url: str,
#     file: str,
#     user: Optional[str] = None,
#     token_info: Dict = Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     token(db, Company_Portal_Url).checktoken(token_info["Id"])
#     media_manager = MediaManager(db, token_info, Company_Portal_Url)
#     result = await media_manager.get_media(file, user)
#     return result
    

@user_router.post("/timeSheets/", operation_id="create_time_sheet")
async def create_time_sheet(
    request: Request,
    data: TimesheetSchema,
    token_info: Dict = Depends(decode_token),
    db: Session = Depends(get_db),
):
    print("data-------",data)
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
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
    token_info: Dict = Depends(decode_token),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
    db: Session = Depends(get_db),
    filterBy: Optional[str] = Query(None),
):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        time_sheet_manager = ViewTimeSheetManager(db, Company_Portal_Url, token_info)
        res ={}
        if user_ids:
            user_ids = [int(id) for id in user_ids.split(",")]
            user_uuid_fetcher = GetUser(db, Company_Portal_Url)
            user_uuids = user_uuid_fetcher.get_user_uuids(user_ids)
            result= time_sheet_manager.get_time_sheets(Day, Week, Month, user_uuids, pagenum=pagenum, sortBy=sortBy, order=order, filterBy=filterBy)
        else:
            result= time_sheet_manager.get_time_sheets(Day, Week, Month, param=param, pagenum=pagenum, own=own, sortBy=sortBy, order=order, filterBy=filterBy)
        
        
        return result
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.put("/timeSheets/", operation_id="update_time_sheet")
async def update_time_sheet(data: UpdateTimeSheet, token_info: Dict = Depends(decode_token), db: Session = Depends(get_db)):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    time_sheet_manager = CreateTimeSheetManager(db, token_info, data.Company_Portal_Url)
    return time_sheet_manager.update_time_sheet(data)


@user_router.delete("/timeSheets/", operation_id="delete_time_sheets")
async def delete_time_sheets(data: DeleteTimeSheet, token_info: Dict = Depends(decode_token), db: Session = Depends(get_db)):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    time_sheet_manager = CreateTimeSheetManager(db, token_info, data.Company_Portal_Url)
    return time_sheet_manager.delete_time_sheets(data)


@user_router.get("/timeSheets/count/", response_model=List[TimesheetCountResponse])
async def get_timesheet_counts(
    Company_Portal_Url: str,
    year: int = None,
    token_info: Dict = Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    service = TimesheetCountService(db, token_info, Company_Portal_Url)
    return service.get_timesheet_counts(year)


@user_router.post("/request/", operation_id="request-create")
async def create_request(data: RequestSchema, token_info: Dict = Depends(decode_token), db: Session = Depends(get_db)):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        request_manager = RequestManager(db, token_info)
        response = await request_manager.create_request(data)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.get("/request/{path_suffix:path}", operation_id="request-get")
async def create_request(
    Company_Portal_Url: str,
    Type: Optional[str] = None,
    user_ids: Optional[str] = None,
    path_suffix: str = "",
    pagenum: Optional[int] = None,
    own: Optional[int] =None,
    token_info: Dict = Depends(decode_token),
    db: Session = Depends(get_db),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
    Status: Optional[str] = None,
):
    try:
        print("Own from Payload: ", own != 1)
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        request_manager = RequestManager(db, token_info)
        if user_ids:
            user_ids = [int(id) for id in user_ids.split(",")]
            user_uuid_fetcher = GetUser(db, Company_Portal_Url)
            user_uuids = user_uuid_fetcher.get_user_uuids(user_ids)
            return request_manager.get_requests(Company_Portal_Url, Type, user_uuids, pagenum=pagenum, own=own, sortBy=sortBy, order=order, Status=Status)
        response = request_manager.get_requests(Company_Portal_Url, Type, path_suffix=path_suffix, pagenum=pagenum, own=own, sortBy=sortBy, order=order, Status=Status)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.put("/request/", operation_id="request-update")
async def update_request_route(
    data: UpdateRequestSchema,
    ID: int,
    token_info: Dict = Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        request_manager = RequestManager(db, token_info)
        response = request_manager.update_request(data, id=ID)
        return response
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.delete("/request/", operation_id="request-delete")
async def delete_request_route(data: DeleteRequest, token_info: Dict = Depends(decode_token), db: Session = Depends(get_db)):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        request_manager = RequestManager(db, token_info)
        return await request_manager.delete_request(data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.get("/request_counts/", operation_id="get_request_counts")
async def get_request_counts(
    Company_Portal_Url: str,
    Day: Optional[str] = None,
    Week: Optional[str] = None,
    Month: Optional[str] = None,
    Type: Optional[str] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    service = RequestCountsService(db, token_info, Company_Portal_Url)
    return service.get_request_counts(Day, Week, Month, Type)


@user_router.get("/notification/")
async def getNotification(Company_Portal_Url: str, token_info=Depends(decode_token), db: Session = Depends(get_db)):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        cust = CustomerUserVerifier(db)
        customer = cust._get_customer(Company_Portal_Url)
        notification = ManageNotification(db, customer)
        return await notification.get_notification(token_info)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.put("/notification/")
async def update_notification(
    Company_Portal_Url: str,
    payload: UpdateNotification,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db)
):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        cust = CustomerUserVerifier(db)
        customer = cust._get_customer(Company_Portal_Url)
        notification = ManageNotification(db, customer)

        print("Payload: ", payload)

        await notification.update_notification(payload.notification_ids, payload.read)
        return {"status": "success", "message": f"Notification{'s' if len(payload.notification_ids) > 1 else ''} updated successfully."}
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        raise e


@user_router.get("/getUserHoliday/")
async def getHolidayUser(Company_Portal_Url: str, ID: Optional[str] = None, token_info=Depends(decode_token), db: Session = Depends(get_db)):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    return await ManageHolidayPolicy(db, token_info).getUserHoliday(Company_Portal_Url)


@user_router.post("/reportbgv/")
def createreport(Company_Portal_Url: str, token_info=Depends(decode_token), db: Session = Depends(get_db)):
    UserBGVManager(db).create_bgv_report(token_info['Id'], Company_Portal_Url)
    token(db, Company_Portal_Url).checktoken(token_info["Id"])


@user_router.get("/remaining-hours/")
async def get_rem_hours(Company_Portal_Url: str,  token_info=Depends(decode_token), db: Session = Depends(get_db)):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    own = 1
    request_manager = RequestManager(db, token_info)
    holiday = ManageHolidayPolicy(db, token_info)
    tim = ViewTimeSheetManager(db, Company_Portal_Url, token_info)

    print("request_manager:---", request_manager)
    
    current_date = datetime.now()
    start_date = (current_date - relativedelta(months=2)).replace(day=1)
    end_date = current_date.replace(day=calendar.monthrange(current_date.year, current_date.month)[1])
    
    months_to_fetch = []
    temp_date = start_date
    while temp_date <= end_date:
        months_to_fetch.append(temp_date.strftime('%Y-%m'))
        temp_date += relativedelta(months=1)
    
    req_data = request_manager.get_requests(Company_Portal_Url, request_type="TimeOff", path_suffix="REQTOF", own=own)
    
    if not isinstance(req_data, list):
        req_data = [req_data] if isinstance(req_data, dict) else []
    
    processed_req_data = [
        {
            "REQN": req.get("REQN", ""),
            "RequestDetails": req.get("RequestDetails", {}),
            "RequestStatus": req.get("RequestStatus", "")
        } 
        for req in req_data
    ]
    
    reqtm_data = [
        {
            "REQN": req.get("REQN", ""),
            "RequestDetails": req.get("RequestDetails", {}),
            "RequestStatus": req.get("RequestStatus", "")
        } 
        for req in request_manager.get_requests(Company_Portal_Url, request_type="TimeSheet", path_suffix="REQTIM", own=own)
    ]
    
    h_data = await holiday.getUserHoliday(Company_Portal_Url)
    
    timesheet_data = []
    for month in months_to_fetch:
        month_data = tim.get_time_sheets(day=month, own =own)
        timesheet_data.extend(month_data if isinstance(month_data, list) else [month_data])
    
    response_data = {
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "months_included": months_to_fetch
        },
        "time_off_requests": processed_req_data,
        "missed_timesheet": reqtm_data,
        "holiday_policy": h_data,
        "timesheets": timesheet_data
    }
    
    return response_data