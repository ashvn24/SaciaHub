"""
Admin management endpoints.
Preserves all original route paths under /v1/admin.
"""

import io
import os
import zipfile
from typing import List, Optional

import markdown
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.dependencies.auth import get_current_user
from src.dependencies.permissions import require_admin
from src.models.database import get_db
from src.repositories.token import TokenRepository
from src.schemas.client import ClientSchema
from src.schemas.document import FileSchema, FolderSchema
from src.schemas.notification import TenantNotificationSettings
from src.schemas.partner import PartnerSchema
from src.schemas.project import ProjectSchema
from src.schemas.request import Report, RequestStatusSchema
from src.schemas.salary import SalarySchema, SalarySplit
from src.schemas.sow import SOWSchema
from src.schemas.timeoff import HolidayScheme, TimeOffPolicySchema
from src.schemas.timesheet import TimpolicySchema, UpdateTimesheet
from src.schemas.user import AssignClientSchema
from src.schemas.bgv import verification

logger = get_logger("api.admin")

admin_router = APIRouter(prefix="/v1/admin", tags=["Admin"])


def _check_token(db: Session, portal_url: str, user_id: str) -> None:
    """Validate user token for the given tenant."""
    token_repo = TokenRepository(db, portal_url)
    token_repo.check_token(user_id)


# ──────────────────────── Timesheet Report ────────────────────────

@admin_router.post("/timesheetReport/")
async def get_report(
    data: Report,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.GetUser import GetUser
    from Models.Classes.Report import ReportGenerator
    from Models.Classes.TimesheetManager import ViewTimeSheetManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    require_admin(token_info)

    if data.users:
        user_uuid_fetcher = GetUser(db, data.Company_Portal_Url)
        user_uuids = user_uuid_fetcher.get_user_uuids(data.users)

    timesheet = ViewTimeSheetManager(db, data.Company_Portal_Url, token_info)
    timesheet_by_date = timesheet.get_time_sheets(user_ids=user_uuids, Date=data.StartDate)
    report_generator = ReportGenerator(timesheet_by_date)
    files = report_generator.get_files()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("timesheet_report.pdf", files["pdf"][1])
        if "csv" in files:
            zf.writestr("timesheet_report.csv", files["csv"][1])
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=timesheet_report.zip"},
    )


# ──────────────────────── TimeOff Policy ────────────────────────

@admin_router.get("/timeoffTemplates/")
async def get_timeoff_policy(
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
):
    from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy

    timeoff_policy = ManageTimeoffPolicy(db, token_info)
    return timeoff_policy.get_timeoff_policy_template(params=ID, sortBy=sortBy, order=order)


@admin_router.post("/timeoffPolicy/", operation_id="create_policy_unique")
async def create_policy(
    data: TimeOffPolicySchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy

    _check_token(db, data.Company_portal_Url, token_info["Id"])
    timeoffpolicy = ManageTimeoffPolicy(db, token_info)
    return await timeoffpolicy.create_timeoff_policy(data)


@admin_router.put("/timeoffPolicy/", operation_id="update-policy")
async def update_timeoff_policy(
    data: TimeOffPolicySchema,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy

    _check_token(db, data.Company_portal_Url, token_info["Id"])
    timeoffpolicy = ManageTimeoffPolicy(db, token_info)
    return await timeoffpolicy.update_timeoff_policy(data, ID)


@admin_router.delete("/timeoffPolicy/", operation_id="delete-policy")
async def delete_timeoff_policy(
    ID: int,
    Company_portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    timeoffpolicy = ManageTimeoffPolicy(db, token_info)
    return await timeoffpolicy.delete_policy(Company_portal_Url, ID)


@admin_router.get("/timeoffPolicy/", operation_id="view-policy")
async def view_timeoff_policy(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    timeoffpolicy = ManageTimeoffPolicy(db, token_info)
    return await timeoffpolicy.get_timeoff_policy(Company_portal_Url, ID)


@admin_router.post("/assignTimeoffpolicy/")
async def assign_timeoff_policy(
    ID: int,
    policyID: int,
    Company_portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TimeOffPolicy import ManageTimeoffPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    timeoffpolicy = ManageTimeoffPolicy(db, token_info)
    return await timeoffpolicy.assign_policy(Company_portal_Url, ID, policyID)


# ──────────────────────── Holiday Policy ────────────────────────

@admin_router.get("/getholidaytemplates/")
async def get_holiday_templates(
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    holiday_policy = ManageHolidayPolicy(db, token_info)
    return holiday_policy.get_holiday_policy_template(params=ID)


@admin_router.post("/holidaypolicy/", operation_id="create-holiday-policy")
async def create_holiday_policy(
    data: HolidayScheme,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, data.Company_portal_Url, token_info["Id"])
    holiday_policy = ManageHolidayPolicy(db, token_info)
    return await holiday_policy.create_policy(data)


@admin_router.put("/holidaypolicy/", operation_id="update-holiday-policy")
async def update_holiday_policy(
    data: HolidayScheme,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, data.Company_portal_Url, token_info["Id"])
    holiday_policy = ManageHolidayPolicy(db, token_info)
    return await holiday_policy.update_policy(data, ID)


@admin_router.get("/holidaypolicy/", operation_id="get-holiday-policy")
async def get_holiday_policy(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    holiday_policy = ManageHolidayPolicy(db, token_info)
    return await holiday_policy.get_holiday_policy(Company_portal_Url, ID, sortBy, order)


@admin_router.delete("/holidaypolicy/", operation_id="delete-holiday-policy")
async def delete_holiday_policy(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    holiday_policy = ManageHolidayPolicy(db, token_info)
    return await holiday_policy.delete_policy(Company_portal_Url, ID)


@admin_router.post("/assignholidaypolicy/")
async def assign_holiday_policy(
    request: Request,
    ID: int,
    policyID: int,
    Company_portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    timeoffpolicy = ManageHolidayPolicy(db, token_info, request)
    return await timeoffpolicy.assign_policy(Company_portal_Url, ID, policyID)


@admin_router.get("/getholidaypolicydetails/")
async def get_holiday_policy_detail(
    Company_portal_Url: str,
    policyID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, Company_portal_Url, token_info["Id"])
    holiday_policy = ManageHolidayPolicy(db, token_info)
    return await holiday_policy.populate_timesheet(Company_portal_Url, policyID)


@admin_router.get("/getTimeoffRequests/")
async def get_timeoff_requests(
    Company_Portal_Url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.HolidayPolicy import ManageHolidayPolicy

    _check_token(db, Company_Portal_Url, token_info["Id"])
    user_manager = ManageHolidayPolicy(db, token_info)
    return user_manager.get_approved_timeoff(Company_Portal_Url)


@admin_router.post("/RequestStatus/")
async def update_request_status(
    request: Request,
    data: RequestStatusSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.RequestManager import RequestManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    user_manager = RequestManager(db, token_info, request)
    return await user_manager.approve_request(data.Company_Portal_Url, data.ID, data.Choice)


# ──────────────────────── Timesheet Policy ────────────────────────

@admin_router.post("/timpolicy/", operation_id="create-timesheet-policy")
async def create_timpolicy(
    data: TimpolicySchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ClientManager import ClientManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    client_manager = ClientManager(db, token_info, data.Company_Portal_Url)
    return await client_manager.createTimesheetPolicy(data)


# ──────────────────────── Client Management ────────────────────────

@admin_router.post("/clients/", operation_id="create-client")
async def create_client(
    client_data: ClientSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ClientManager import ClientManager

    _check_token(db, client_data.Company_Portal_Url, token_info["Id"])
    client_manager = ClientManager(db, token_info, client_data.Company_Portal_Url)
    return client_manager.create_client(client_data)


@admin_router.get("/clients/", operation_id="get-client")
async def get_clients(
    Company_Portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ClientManager import ClientManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    client_manager = ClientManager(db, token_info, Company_Portal_Url)
    return client_manager.get_client(ID)


@admin_router.put("/clients/", operation_id="update-client")
async def update_client(
    client_data: ClientSchema,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ClientManager import ClientManager

    _check_token(db, client_data.Company_Portal_Url, token_info["Id"])
    client_manager = ClientManager(db, token_info, client_data.Company_Portal_Url)
    return client_manager.update_client(ID, client_data)


@admin_router.delete("/clients/", operation_id="delete-client")
async def delete_client(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ClientManager import ClientManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    client_manager = ClientManager(db, token_info, Company_Portal_Url)
    return client_manager.delete_client(ID)


@admin_router.post("/assignClient/")
async def assign_client(
    data: AssignClientSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ClientManager import ClientManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    client_manager = ClientManager(db, token_info, data.Company_Portal_Url)
    return client_manager.assign_client(data.UserID, data.ClientID, data.ProjectID)


# ──────────────────────── Project Management ────────────────────────

@admin_router.post("/projects/", operation_id="create-project")
async def create_project(
    project_data: ProjectSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ProjectManager import ProjectManager

    _check_token(db, project_data.Company_Portal_Url, token_info["Id"])
    project_manager = ProjectManager(db, token_info, project_data.Company_Portal_Url)
    return project_manager.create_project(project_data)


@admin_router.get("/projects/", operation_id="get-project")
async def get_projects(
    Company_Portal_Url: str,
    ClientID: Optional[int] = None,
    VendorID: Optional[int] = None,
    PartnerID: Optional[int] = None,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ProjectManager import ProjectManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    project_manager = ProjectManager(db, token_info, Company_Portal_Url)
    return project_manager.get_project(ID, ClientID, VendorID, PartnerID)


@admin_router.put("/projects/", operation_id="update-project")
async def update_project(
    project_data: ProjectSchema,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ProjectManager import ProjectManager

    _check_token(db, project_data.Company_Portal_Url, token_info["Id"])
    project_manager = ProjectManager(db, token_info, project_data.Company_Portal_Url)
    return project_manager.update_project(ID, project_data)


@admin_router.delete("/projects/", operation_id="delete-project")
async def delete_project(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.ProjectManager import ProjectManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    project_manager = ProjectManager(db, token_info, Company_Portal_Url)
    return project_manager.delete_project(ID)


# ──────────────────────── SOW Management ────────────────────────

@admin_router.post("/sow/", operation_id="create-sow")
async def create_sow(
    sow_data: SOWSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.SOWManager import SOWManager

    _check_token(db, sow_data.Company_Portal_Url, token_info["Id"])
    sow_manager = SOWManager(db, token_info, sow_data.Company_Portal_Url)
    return sow_manager.create_sow(sow_data)


@admin_router.get("/sow/", operation_id="get-sow")
async def get_sow(
    Company_Portal_Url: str,
    ID: Optional[int] = None,
    ProjectID: Optional[int] = None,
    ClientID: Optional[int] = None,
    VendorID: Optional[int] = None,
    PartnerID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.SOWManager import SOWManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    sow_manager = SOWManager(db, token_info, Company_Portal_Url)
    return sow_manager.get_sow(ID, ProjectID, ClientID, PartnerID, VendorID)


@admin_router.put("/sow/", operation_id="update-sow")
async def update_sow(
    sow_data: SOWSchema,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.SOWManager import SOWManager

    _check_token(db, sow_data.Company_Portal_Url, token_info["Id"])
    sow_manager = SOWManager(db, token_info, sow_data.Company_Portal_Url)
    return sow_manager.update_sow(ID, sow_data)


@admin_router.delete("/sow/", operation_id="delete-sow")
async def delete_sow(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.SOWManager import SOWManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    sow_manager = SOWManager(db, token_info, Company_Portal_Url)
    return sow_manager.delete_sow(ID)


# ──────────────────────── Vendor Management ────────────────────────

@admin_router.post("/vendors/", operation_id="create-vendor")
async def create_vendor(
    vendor_data: "VendorSchema",
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.VendorManager import VendorManager
    from src.schemas.vendor import VendorSchema  # noqa: F811

    _check_token(db, vendor_data.Company_Portal_Url, token_info["Id"])
    vendor_manager = VendorManager(db, token_info, vendor_data.Company_Portal_Url)
    return vendor_manager.create_vendor(vendor_data)


@admin_router.get("/vendors/", operation_id="get-vendor")
async def get_vendors(
    Company_Portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.VendorManager import VendorManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    vendor_manager = VendorManager(db, token_info, Company_Portal_Url)
    return vendor_manager.get_vendor(ID)


@admin_router.put("/vendors/", operation_id="update-vendor")
async def update_vendor(
    vendor_data: "VendorSchema",
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.VendorManager import VendorManager
    from src.schemas.vendor import VendorSchema  # noqa: F811

    _check_token(db, vendor_data.Company_Portal_Url, token_info["Id"])
    vendor_manager = VendorManager(db, token_info, vendor_data.Company_Portal_Url)
    return vendor_manager.update_vendor(ID, vendor_data)


@admin_router.delete("/vendors/", operation_id="delete-vendor")
async def delete_vendor(
    Company_Portal_Url: str,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.VendorManager import VendorManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    vendor_manager = VendorManager(db, token_info, Company_Portal_Url)
    return vendor_manager.delete_vendor(ID)


# ──────────────────────── Partner Management ────────────────────────

@admin_router.post("/partners/", operation_id="create-partner")
async def create_partner(
    data: PartnerSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.PartnerManager import PartnerManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    partner_manager = PartnerManager(db, token_info, data.Company_Portal_Url)
    return partner_manager.create_partner(data)


@admin_router.get("/partners/", operation_id="get-partner")
async def get_partner(
    Company_portal_Url: str,
    ID: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.PartnerManager import PartnerManager

    _check_token(db, Company_portal_Url, token_info["Id"])
    partner_manager = PartnerManager(db, token_info, Company_portal_Url)
    return partner_manager.get_partner(ID)


@admin_router.put("/partners/", operation_id="update-partner")
async def update_partner(
    data: PartnerSchema,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.PartnerManager import PartnerManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    partner_manager = PartnerManager(db, token_info, data.Company_Portal_Url)
    return partner_manager.update_partner(ID, data)


@admin_router.delete("/partners/", operation_id="delete-partner")
async def delete_partner(
    Company_portal_Url: str,
    ID: int,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.PartnerManager import PartnerManager

    _check_token(db, Company_portal_Url, token_info["Id"])
    partner_manager = PartnerManager(db, token_info, Company_portal_Url)
    return partner_manager.delete_partner(ID)


# ──────────────────────── Document Management ────────────────────────

@admin_router.post("/createFolder/")
async def create_folder(
    data: FolderSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.folderManager import FolderManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    folder_manager = FolderManager(db, token_info, data.Company_Portal_Url)
    return folder_manager.create_folder(data)


@admin_router.get("/getfolders/")
async def get_folders(
    Company_Portal_Url: str,
    folder_id: Optional[int] = None,
    entityType: Optional[str] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.folderManager import FolderManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    folder_manager = FolderManager(db, token_info, Company_Portal_Url)
    return folder_manager.get_sub_folders(folder_id, entityType)


@admin_router.post("/createFile/")
async def create_file(
    data: FileSchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.folderManager import FolderManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    folder_manager = FolderManager(db, token_info, data.Company_Portal_Url)
    return folder_manager.create_file(data)


@admin_router.get("/getFiles/")
async def get_files(
    Company_Portal_Url: str,
    folder_id: Optional[int] = None,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.folderManager import FolderManager

    _check_token(db, Company_Portal_Url, token_info["Id"])
    folder_manager = FolderManager(db, token_info, Company_Portal_Url)
    return folder_manager.get_files_of_folder(folder_id)


# ──────────────────────── BGV Verification ────────────────────────

@admin_router.get("/bgvVerification/", operation_id="get-bgv-verification")
async def get_bgv_verification(
    data: verification,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.VerificationManager import Verification
    from src.utils.serializer import serialize_non_null_data

    user = await Verification(db=db, data=data, token_info=token_info).get_user()
    html_content = serialize_non_null_data(user)
    return HTMLResponse(content=html_content)


@admin_router.post("/bgvVerification/", operation_id="create-bgv-verification")
async def bgv_verification(
    data: verification,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.VerificationManager import Verification

    verifier = Verification(db=db, data=data, token_info=token_info)
    return await verifier.process()


# ──────────────────────── Salary ────────────────────────

@admin_router.post("/getsalaryspilt/", operation_id="get-salary-split")
async def get_salary_split(
    data: SalarySchema,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.SalarySplit import SalaryManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    return await SalaryManager(db, data.Company_Portal_Url, token_info).getsalarySplit(data.Amount_CTC)


@admin_router.post("/createSalarySplit/", operation_id="create-salary-split")
async def create_salary_split(
    data: SalarySplit,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.SalarySplit import SalaryManager

    _check_token(db, data.Company_Portal_Url, token_info["Id"])
    return await SalaryManager(db, data.Company_Portal_Url, token_info).createSalarySplit(data)


# ──────────────────────── Employment History ────────────────────────

@admin_router.get("/get-employment-history/", operation_id="get-employment-history")
async def get_employment_history(
    company_portal_url: str,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
    pageNum: Optional[int] = None,
    own: Optional[int] = None,
    sortBy: Optional[str] = None,
    order: Optional[int] = 1,
):
    from Models.Classes.userbgvManager import UserBGVManager

    _check_token(db, company_portal_url, token_info["Id"])
    return await UserBGVManager(db, company_portal_url).get_employment_history(pageNum, own, sortBy, order)


# ──────────────────────── Tenant Settings ────────────────────────

@admin_router.put("/update-tenant-notifications/", operation_id="update-tenant-notification")
async def update_tenant_settings(
    company_portal_url: str,
    settings: TenantNotificationSettings,
    token_info=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from Models.Classes.TenantSettings import TenantSettingsManager

    _check_token(db, company_portal_url, token_info["Id"])
    tenant_settings_manager = TenantSettingsManager(db, company_portal_url)
    result = await tenant_settings_manager.update_notification_settings(
        timesheet_notification=settings.timesheet_notification,
        request_notification=settings.request_notification,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "Success", "message": result["message"]},
    )


# ──────────────────────── Documentation ────────────────────────

README_PATH = os.path.join(os.path.dirname(__file__), "../../../../README.md")


@admin_router.get("/documentation/", response_class=HTMLResponse, tags=["General"])
async def get_readme():
    try:
        with open(README_PATH, "r", encoding="utf-8") as file:
            md_content = file.read()
        html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables", "codehilite"])
        html = f"""<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>SaciaHub API Documentation</title>
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
                <style>
                    body {{ box-sizing: border-box; min-width: 200px; max-width: 1200px; margin: 0 auto; padding: 45px;
                           font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; color: #24292e; }}
                    .markdown-body {{ box-sizing: border-box; min-width: 200px; max-width: 1200px; margin: 0 auto; padding: 45px; }}
                    @media (max-width: 767px) {{ .markdown-body {{ padding: 15px; }} }}
                    pre {{ background-color: #f6f8fa; border-radius: 6px; padding: 16px; overflow: auto; }}
                    code {{ font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace; padding: 0.2em 0.4em; font-size: 85%;
                           background-color: rgba(27, 31, 35, 0.05); border-radius: 6px; }}
                </style>
            </head>
            <body class="markdown-body">{html_content}</body>
            </html>"""
        return HTMLResponse(content=html, status_code=200)
    except FileNotFoundError:
        return HTMLResponse("<h1>README.md not found</h1>", status_code=404)
