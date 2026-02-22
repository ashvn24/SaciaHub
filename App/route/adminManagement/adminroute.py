import io
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Request, status
import logging
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from Models.utils.tokenmanage import token
from Models.Classes.VerificationManager import Verification
from Models.Classes.SalarySplit import SalaryManager
from Models.utils.serializer import serialize_non_null_data
from Models.Classes.userbgvManager import UserBGVManager
from Models.Classes.folderManager import FolderManager
from Models.Classes.PartnerManager import PartnerManager
from Models.Classes.UserManager import UserAuthManager
from Models.Classes.VendorManager import VendorManager
from Models.Classes.SOWManager import SOWManager
from Models.Classes.ProjectManager import ProjectManager
from Models.Classes.ClientManager import ClientManager
from Models.Classes.RequestManager import RequestManager
from Models.Classes.AdminUserManager import UserManager
from Models.Classes.HolidayPolicy import ManageHolidayPolicy
from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy
from Models.Classes.Report import ReportGenerator, TimesheetReportManager
from Models.Classes.TenantSettings import TenantSettingsManager
from Models.Classes.GetUser import GetUser
from Models.Classes.TimesheetManager import ViewTimeSheetManager, TimesheetManagerStatus
from Models.Classes.customerVerifier import CustomerUserVerifier
from Models.db.schemas import (
    AdminTimesheet,
    AssignClientSchema,
    BritsUserSchema,
    ClientSchema,
    DeleteUser,
    FileSchema,
    FolderSchema,
    HolidayScheme,
    PartnerSchema,
    ProjectSchema,
    Report,
    RequestStatusSchema,
    SOWSchema,
    SalarySchema,
    SalarySplit,
    TimeOffPolicySchema,
    TimpolicySchema,
    UpdateTimesheet,
    VendorSchema,
    bgvReportSchema,
    verification,
    TenantNotificationSettings
)
from Models.Classes.token_authentication import decode_token
from Models.db.db_connection import SessionLocal
from sqlalchemy.orm import Session
from typing import Optional, List
from Models.db.schemas import EmploymentHistorySchema
import markdown
import io
import zipfile
import os
from Models.utils.error_handler import ErrorHandler

logger = logging.getLogger(__name__)
error = ErrorHandler()

admin_router = APIRouter(prefix="/v1/admin", tags=["Admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_admin(token_info):
    if not token_info["role"] in ["Admin", "Manager", "HR"]:
        error.error("You do not have the permission to perform this action", 401, "Admin Check")


# @admin_router.patch("/status/")
# async def update_user_status_route(
#     ID: str,
#     Company_Portal_Url: str,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     token(db, Company_Portal_Url).checktoken(token_info["Id"])
#     user_manager = UserManager(db)
#     return await user_manager.update_user_status(ID, Company_Portal_Url, token_info)


# @admin_router.post("/register/")
# async def user_register_route(
#     data: BritsUserSchema,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
#     user_manager = UserManager(db)
#     return await user_manager.register_user(data, token_info)

# @admin_router.get("/impersonate/")
# async def  ImpersonateRole(
#     Company_Portal_Url: str,
#     userID: int,
#     token_info = Depends(decode_token),
#     db: Session = Depends(get_db)
# ):
#     token(db, Company_Portal_Url).checktoken(token_info["Id"])
#     user = UserAuthManager(db, Company_Portal_Url)
#     return user.impersonate_role(Company_Portal_Url, token_info, userID)


# @admin_router.post("/TimesheetReport/")
# async def admin_timesheet_route(
#     data: AdminTimesheet,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
#     report_manager = TimesheetReportManager(db)
#     return await report_manager.admin_timesheet(data, token_info)


# @admin_router.put("/TimesheetStatus/")
# async def approve_timesheet(
#     data: UpdateTimesheet,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     try:
#         token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
#         verifier = CustomerUserVerifier(db)
#         result = verifier.verify_customer_and_user(
#             data.Company_Portal_Url, token_info["Id"]
#         )
#         if isinstance(result, JSONResponse):
#             return result  # This is an error response
#         customer, user = result

#         timesheet_manager = TimesheetManagerStatus(db)
#         print("data")
#         return await timesheet_manager.approve_timesheet(data, token_info, customer)
#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         logger.error(f"An unexpected error occurred: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail="An unexpected error"
#         )


# @admin_router.get("/getUsers/")
# async def getUSers(
#     company_portal_url: str,
#     token_info=Depends(decode_token),
#     userID: Optional[int] = None,
#     sortby: Optional[str] = None,
#     db: Session = Depends(get_db),
# ):
#     try:
#         token(db, company_portal_url).checktoken(token_info["Id"])
#         user = GetUser(db, company_portal_url)
#         users = user.get_all_users(token_info, userID, sortby)
#         return users
#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         logger.error(f"An unexpected error occurred: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail="An unexpected error"
#         )

# @admin_router.delete("/deleteUser/")
# async def deleteUser(
#     data: DeleteUser,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     try:
#         token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
#         user = GetUser(db, data.Company_Portal_Url)
#         users = user.delete_users(data.User_ID, token_info)
#         return users
#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         logger.error(f"An unexpected error occurred: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail="An unexpected error"
#         )
        
# @admin_router.put("/updateUser/")
# async def updateUser(
#     data: BritsUserSchema,
#     UserID: int,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     try:
#         token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
#         user = UserManager(db)
#         users = user.update_user(UserID, data, token_info)
#         return users
#     except HTTPException as http_exc:
#         raise http_exc
#     except Exception as e:
#         logger.error(f"An unexpected error occurred: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail="An unexpected error"
#         )

@admin_router.post("/timesheetReport/")
async def getReport(
    data: Report, token_info=Depends(decode_token), db: Session = Depends(get_db)
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        is_admin(token_info)
        if data.users:
            user_uuid_fetcher = GetUser(db, data.Company_Portal_Url)
            user_uuids = user_uuid_fetcher.get_user_uuids(data.users)
        timesheet = ViewTimeSheetManager(db, data.Company_Portal_Url, token_info)
        timesheetByDate = timesheet.get_time_sheets(
            user_ids=user_uuids, Date=data.StartDate)
        report_generator = ReportGenerator(timesheetByDate)
        files = report_generator.get_files()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            # Add PDF
            zf.writestr("timesheet_report.pdf", files["pdf"][1])
            # Add CSV if present
            if "csv" in files:
                zf.writestr("timesheet_report.csv", files["csv"][1])

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=timesheet_report.zip"
            },
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timesheet Report Generate Error", str(e))
        raise e


# ---------------------------------------------------------TimeOff Policy------------------------------------------------


@admin_router.get("/timeoffTemplates/")
async def get_timeoff_policy(
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
):
    try:
        timeoff_policy = ManageTimeoffPolicy(db, token_info)
        policy_templates = timeoff_policy.get_timeoff_policy_template(
            params=ID, sortBy=sortBy, order=order)
        return policy_templates
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timeoff Policy Get Error", str(e))
        raise e


@admin_router.post("/timeoffPolicy/", operation_id="create_policy_unique")
async def create_policy(
    data: TimeOffPolicySchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_portal_Url).checktoken(token_info["Id"])
        timeoffpolicy = ManageTimeoffPolicy(db, token_info)
        return await timeoffpolicy.create_timeoff_policy(data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timeoff Policy Create Error", str(e))
        raise e


@admin_router.put("/timeoffPolicy/", operation_id="update-policy")
async def update_policy(
    data: TimeOffPolicySchema,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):

    try:
        token(db, data.Company_portal_Url).checktoken(token_info["Id"])
        timeoffpolicy = ManageTimeoffPolicy(db, token_info)
        return await timeoffpolicy.update_timeoff_policy(data, ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timeoff Policy Update Error", str(e))
        raise e


@admin_router.delete("/timeoffPolicy/", operation_id="delete-policy")
async def update_policy(
    ID: int,
    Company_portal_Url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):

    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        timeoffpolicy = ManageTimeoffPolicy(db, token_info)
        return await timeoffpolicy.delete_policy(Company_portal_Url, ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timeoff Policy Delete Error", str(e))
        raise e


@admin_router.get("/timeoffPolicy/", operation_id="view-policy")
async def update_policy(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):

    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        timeoffpolicy = ManageTimeoffPolicy(db, token_info)
        return await timeoffpolicy.get_timeoff_policy(Company_portal_Url, ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timeoff Policy View Error", str(e))
        raise e


@admin_router.post("/assignTimeoffpolicy/")
async def assignpolicy(
    ID: int,
    policyID: int,
    Company_portal_Url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        timeoffpolicy = ManageTimeoffPolicy(db, token_info)
        return await timeoffpolicy.assign_policy(Company_portal_Url, ID, policyID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Timeoff Policy Assign Error", str(e))
        raise e


# ------------------------------------------- Holiday Policy-----------------------------------------------------


@admin_router.get("/getholidaytemplates/")
async def getholidaypolicy(
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        holiday_policy = ManageHolidayPolicy(db, token_info)
        policy_templates = holiday_policy.get_holiday_policy_template(
            params=ID)
        return policy_templates
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Get Error", str(e))
        raise e


@admin_router.post("/holidaypolicy/", operation_id="create-holiday-policy")
async def createpolicy(
    data: HolidayScheme, token_info=Depends(decode_token), db: Session = Depends(get_db)
):
    try:
        token(db, data.Company_portal_Url).checktoken(token_info["Id"])
        holiday_policy = ManageHolidayPolicy(db, token_info)
        return await holiday_policy.create_policy(data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Create Error", str(e))
        raise e


@admin_router.put("/holidaypolicy/", operation_id="update-holiday-policy")
async def createpolicy(
    data: HolidayScheme,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_portal_Url).checktoken(token_info["Id"])
        holiday_policy = ManageHolidayPolicy(db, token_info)
        return await holiday_policy.update_policy(data, ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Update Error", str(e))
        raise e


@admin_router.get("/holidaypolicy/", operation_id="get-holiday-policy")
async def createpolicy(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
):
    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        holiday_policy = ManageHolidayPolicy(db, token_info)
        return await holiday_policy.get_holiday_policy(Company_portal_Url, ID, sortBy, order)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Get Error", str(e))
        raise e


@admin_router.delete("/holidaypolicy/", operation_id="delete-holiday-policy")
async def createpolicy(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        holiday_policy = ManageHolidayPolicy(db, token_info)
        return await holiday_policy.delete_policy(Company_portal_Url, ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Delete Error", str(e))
        raise e


@admin_router.post("/assignholidaypolicy/")
async def assignpolicy(
    request: Request,
    ID: int,
    policyID: int,
    Company_portal_Url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        timeoffpolicy = ManageHolidayPolicy(db, token_info, request)
        return await timeoffpolicy.assign_policy(Company_portal_Url, ID, policyID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Assign Error", str(e))
        raise e


@admin_router.get("/getholidaypolicydetails/")
async def getholidaypolicydetail(
    Company_portal_Url: str,
    policyID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_portal_Url).checktoken(token_info["Id"])
        holiday_policy = ManageHolidayPolicy(db, token_info)
        return await holiday_policy.populate_timesheet(Company_portal_Url, policyID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

@admin_router.get("/getTimeoffRequests/")
async def get_timeoff_requests(
    Company_Portal_Url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        user_manager = ManageHolidayPolicy(db, token_info)
        return user_manager.get_approved_timeoff(Company_Portal_Url)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e


@admin_router.post("/RequestStatus/")
async def update_user_status_route(
    request: Request,
    data: RequestStatusSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        user_manager = RequestManager(db, token_info, request)
        return await user_manager.approve_request(data.Company_Portal_Url, data.ID, data.Choice)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e


#---------------------------------------------------------TimeSheetPolicy---------------------------------------------------------------

@admin_router.post("/timpolicy/", operation_id="create-timesheet-policy")
async def create_timpolicy(
    data: TimpolicySchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db)
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        client_manager = ClientManager(db, token_info, data.Company_Portal_Url)
        return await client_manager.createTimesheetPolicy(data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

#---------------------------------------------------------Client Management------------------------------------------------

@admin_router.post("/clients/", operation_id="create-client")
async def create_client(
    client_data: ClientSchema, 
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, client_data.Company_Portal_Url).checktoken(token_info["Id"])
        client_manager = ClientManager(db, token_info, client_data.Company_Portal_Url)
        return client_manager.create_client(client_data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

@admin_router.get("/clients/", operation_id="get-client")
async def create_client(
    Company_Portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        client_manager = ClientManager(db, token_info,Company_Portal_Url)
        return client_manager.get_client(ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

@admin_router.put("/clients/", operation_id="update-client")
async def create_client(
    client_data: ClientSchema,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, client_data.Company_Portal_Url).checktoken(token_info["Id"])
        client_manager = ClientManager(db, token_info,client_data.Company_Portal_Url)
        return client_manager.update_client(ID, client_data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

@admin_router.delete("/clients/", operation_id="delete-client")
async def create_client(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, Company_Portal_Url).checktoken(token_info["Id"])
        client_manager = ClientManager(db, token_info,Company_Portal_Url)
        return client_manager.delete_client(ID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e

@admin_router.post("/assignClient/")
async def AssignClient(
    data: AssignClientSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
        client_manager = ClientManager(db, token_info, data.Company_Portal_Url)
        return client_manager.assign_client(data.UserID, data.ClientID, data.ProjectID)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e



# ---------------------------------------------------------Project Management------------------------------------------------

@admin_router.post("/projects/", operation_id="create-project")
async def create_project(
    project_data: ProjectSchema, 
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, project_data.Company_Portal_Url).checktoken(token_info["Id"])
    project_manager = ProjectManager(db, token_info, project_data.Company_Portal_Url)
    return project_manager.create_project(project_data)

@admin_router.get("/projects/", operation_id="get-project")
async def create_project(
    Company_Portal_Url: str,
    ClientID: Optional[int] = None,
    VendorID: Optional[int] = None,
    PartnerID: Optional[int] = None,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    project_manager = ProjectManager(db, token_info,Company_Portal_Url)
    return project_manager.get_project(ID, ClientID, VendorID, PartnerID)

@admin_router.put("/projects/", operation_id="update-project")
async def create_project(
    project_data: ProjectSchema,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, project_data.Company_Portal_Url).checktoken(token_info["Id"])
    project_manager = ProjectManager(db, token_info,project_data.Company_Portal_Url)
    return project_manager.update_project(ID, project_data)

@admin_router.delete("/projects/", operation_id="delete-project")
async def create_project(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    project_manager = ProjectManager(db, token_info,Company_Portal_Url)
    return project_manager.delete_project(ID)
    

# ---------------------------------------------------------SOW Management------------------------------------------------

@admin_router.post("/sow/", operation_id="create-sow")
async def create_sow(
    sow_data: SOWSchema, 
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, sow_data.Company_Portal_Url).checktoken(token_info["Id"])
    sow_manager = SOWManager(db, token_info, sow_data.Company_Portal_Url)
    return sow_manager.create_sow(sow_data)

@admin_router.get("/sow/", operation_id="get-sow")
async def create_sow(
    Company_Portal_Url: str,
    ID: Optional[int] = None,
    ProjectID: Optional[int] = None,
    ClientID: Optional[int] = None,
    VendorID: Optional[int] = None,
    PartnerID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    sow_manager = SOWManager(db, token_info,Company_Portal_Url)
    return sow_manager.get_sow(ID, ProjectID, ClientID, PartnerID, VendorID)

@admin_router.put("/sow/", operation_id="update-sow")
async def create_sow(
    sow_data: SOWSchema,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, sow_data.Company_Portal_Url).checktoken(token_info["Id"])
    sow_manager = SOWManager(db, token_info,sow_data.Company_Portal_Url)
    print("\n data", sow_data)
    return sow_manager.update_sow(ID, sow_data)

@admin_router.delete("/sow/", operation_id="delete-sow")
async def create_sow(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    sow_manager = SOWManager(db, token_info,Company_Portal_Url)
    return sow_manager.delete_sow(ID)


#---------------------------------------------------------VendorManager------------------------------------------------

@admin_router.post("/vendors/", operation_id="create-vendor")
async def create_vendor(
    vendor_data: VendorSchema, 
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, vendor_data.Company_Portal_Url).checktoken(token_info["Id"])
    vendor_manager = VendorManager(db, token_info, vendor_data.Company_Portal_Url)
    return vendor_manager.create_vendor(vendor_data)

@admin_router.get("/vendors/", operation_id="get-vendor")
async def create_vendor(
    Company_Portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    vendor_manager = VendorManager(db, token_info,Company_Portal_Url)
    return vendor_manager.get_vendor(ID)

@admin_router.put("/vendors/", operation_id="update-vendor")
async def create_vendor(
    vendor_data: VendorSchema,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, vendor_data.Company_Portal_Url).checktoken(token_info["Id"])
    vendor_manager = VendorManager(db, token_info,vendor_data.Company_Portal_Url)
    return vendor_manager.update_vendor(ID, vendor_data)

@admin_router.delete("/vendors/", operation_id="delete-vendor")
async def create_vendor(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    vendor_manager = VendorManager(db, token_info,Company_Portal_Url)
    return vendor_manager.delete_vendor(ID)



#----------------------------------------------------Partner Routes--------------------------------------------

@admin_router.post("/partners/", operation_id="create-partner")
async def create_partner(
    data: PartnerSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):

    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    partner_manager = PartnerManager(db, token_info, data.Company_Portal_Url)
    return partner_manager.create_partner(data)

@admin_router.get("/partners/", operation_id="get-partner")
async def get_partner(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_portal_Url).checktoken(token_info["Id"])
    partner_manager = PartnerManager(db, token_info, Company_portal_Url)
    return partner_manager.get_partner(ID)

@admin_router.put("/partners/", operation_id="update-partner")
async def update_partner(
    data: PartnerSchema,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    partner_manager = PartnerManager(db, token_info, data.Company_Portal_Url)
    return partner_manager.update_partner(ID, data)

@admin_router.delete("/partners/", operation_id="delete-partner")
async def delete_partner(
    Company_portal_Url: str,
    ID: int,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_portal_Url).checktoken(token_info["Id"])
    partner_manager = PartnerManager(db, token_info, Company_portal_Url)
    return partner_manager.delete_partner(ID)

#--------------------------------------------------Document Management--------------------------------------------

@admin_router.post("/createFolder/")
async def createFolder(
    data: FolderSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    folder_manager = FolderManager(db, token_info, data.Company_Portal_Url)
    return folder_manager.create_folder(data)


@admin_router.get("/getfolders/")
async def getFolders(
    Company_Portal_Url: str,
    folder_id: Optional[int] = None,
    entityType: Optional[str] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    folder_manager = FolderManager(db, token_info, Company_Portal_Url)
    return folder_manager.get_sub_folders(folder_id,entityType)

@admin_router.post("/createFile/")
async def createFile(
    data: FileSchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    folder_manager = FolderManager(db, token_info, data.Company_Portal_Url)
    return folder_manager.create_file(data)

@admin_router.get("/getFiles/")
async def getFiles(
    Company_Portal_Url: str,
    folder_id: Optional[int] = None,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, Company_Portal_Url).checktoken(token_info["Id"])
    folder_manager = FolderManager(db, token_info, Company_Portal_Url)
    return folder_manager.get_files_of_folder(folder_id)

#--------------------------------------------------BGV Verification--------------------------------------------
@admin_router.get("/bgvVerification/", operation_id= "get-bgv-verification" )
async def getBgvVerification(
    data: verification,
    token_info = Depends(decode_token),
    db: Session = Depends(get_db)
):
    user = await Verification(db=db, data=data, token_info=token_info).get_user()
    html_content = serialize_non_null_data(user)
    return HTMLResponse(content=html_content)

@admin_router.post("/bgvVerification/", operation_id="create-bgv-verification")
async def bgv_verification(
    data: verification,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    verifier = Verification(db=db, data=data, token_info=token_info)
    return await verifier.process()

# @admin_router.get("/bgvUsers/")
# def bgvUsers(
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
#     Company_Portal_Url: str = None
# ):
#     token(db, Company_Portal_Url).checktoken(token_info["Id"])
#     is_admin(token_info)
#     users = UserBGVManager(db).get_bgv_users(Company_Portal_Url)
#     return users

# @admin_router.get("/bgvReport/", operation_id="bgv-report")
# def bgvReport(
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
#     user: str = None,
#     Company_Portal_Url: str = None,
# ):
#     token(db, Company_Portal_Url).checktoken(token_info["Id"])
#     is_admin(token_info)
#     users = UserBGVManager(db).get_bgvreport(user, Company_Portal_Url)
#     return users

# @admin_router.put("/bgvReport/", operation_id="bgv-report_update")
# def bgvReport(
#     data: bgvReportSchema,
#     token_info=Depends(decode_token),
#     db: Session = Depends(get_db),
# ):
#     token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
#     is_admin(token_info)
#     users = UserBGVManager(db).update_bgv_report(data.Company_Portal_Url, data.User_ID, data.data)
#     return users

@admin_router.post("/getsalaryspilt/", operation_id="get-salary-split")
async def getSalarySplit(
    data: SalarySchema,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    return await SalaryManager(db, data.Company_Portal_Url, token_info).getsalarySplit(data.Amount_CTC)

@admin_router.post("/createSalarySplit/", operation_id="create-salary-split")
async def createSalarySplit(
    data: SalarySplit,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    token(db, data.Company_Portal_Url).checktoken(token_info["Id"])
    return await SalaryManager(db, data.Company_Portal_Url, token_info).createSalarySplit(data)


@admin_router.get("/get-employment-history/", operation_id="get-employment-history")
async def get_employment_history(
    company_portal_url: str,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
    pageNum: Optional[int] = None,
    own: Optional[int] = None,
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
):
    token(db, company_portal_url).checktoken(token_info["Id"])
    return await UserBGVManager(db, company_portal_url).get_employment_history(pageNum, own, sortBy, order)

@admin_router.put("/update-tenant-notifications/", operation_id="update-tenant-notification")
async def update_tenant_settings(
    company_portal_url: str,
    settings: TenantNotificationSettings,
    token_info=Depends(decode_token),
    db: Session = Depends(get_db),
):
    try:
        token(db, company_portal_url).checktoken(token_info["Id"])
        tenant_settings_manager = TenantSettingsManager(db, company_portal_url)
        print("tenant_settings_manager",tenant_settings_manager)
        result = await tenant_settings_manager.update_notification_settings(
            timesheet_notification=settings.timesheet_notification,
            request_notification=settings.request_notification
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "Success",
                "message": result["message"]
            }
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        print("Holiday Policy Populate Error", str(e))
        raise e


README_PATH = os.path.join(os.path.dirname(__file__), "../../../README.md")

@admin_router.get("/documentation/", response_class=HTMLResponse, tags=["General"])
async def get_readme():
    try:
        with open(README_PATH, "r", encoding="utf-8") as file:
            md_content = file.read()
        html_content = markdown.markdown(md_content,extensions=['fenced_code', 'tables', 'codehilite'])
        html = f"""<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>SaciaHub API Documentation</title>
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
                <style>
                    body {{
                        box-sizing: border-box;
                        min-width: 200px;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 45px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                        line-height: 1.6;
                        color: #24292e;
                    }}
                    .markdown-body {{
                        box-sizing: border-box;
                        min-width: 200px;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 45px;
                    }}
                    @media (max-width: 767px) {{
                        .markdown-body {{
                            padding: 15px;
                        }}
                    }}
                    pre {{
                        background-color: #f6f8fa;
                        border-radius: 6px;
                        padding: 16px;
                        overflow: auto;
                    }}
                    code {{
                        font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
                        padding: 0.2em 0.4em;
                        margin: 0;
                        font-size: 85%;
                        background-color: rgba(27, 31, 35, 0.05);
                        border-radius: 6px;
                    }}
                </style>
            </head>
            <body class="markdown-body">
                {html_content}
            </body>
            </html>"""
        return HTMLResponse(content=html, status_code=200)
    except FileNotFoundError:
        return HTMLResponse("<h1>README.md not found</h1>", status_code=404)