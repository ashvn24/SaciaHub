from pydantic import UUID4, BaseModel, Field, Json
from typing import Any, Dict, List, Optional
from datetime import date, datetime, time
from typing import Union
from sqlalchemy import JSON


class CustomerSchema(BaseModel):

    Company_Name: str
    Contact_FirstName: str
    Contact_LastName: str
    Contact_Email: str
    Contact_PhoneNumber: str
    Company_ShortName: str

    class Config:
        from_attributes = True
        from_attributes = True


class ResetPasswordSchema(BaseModel):
    Company_Shortname: str
    Username: str
    # old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class SignInSchema(BaseModel):
    Company_Portal_Url: str
    username: str
    password: str


class BritsUserSchema(BaseModel):
    Company_Portal_Url: str
    LastName: str
    FirstName: str
    User_Email: str
    User_role: Optional[str] = None
    Job_Role: Optional[str] = None
    module: List[str] = []
    Manager: Optional[int] = None
    HR_Manager: Optional[int] = None
    Team: str

    class Config:
        from_attributes = True
        from_attributes = True

class bgvStatus(BaseModel):
    Company_Portal_Url: str
    useruuid: str
    status: str

class BritsUserBGVSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    FirstName: Optional[str] = None
    LastName: Optional[str] = None
    IsFresher: Optional[bool] = None
    IsUAN: Optional[bool] = None
    isPassport: Optional[bool] =None
    MiddleName: Optional[str] = None
    FatherName: Optional[str] = None
    MobileNumber: Optional[str] = None
    Marital_Status: Optional[str] = None
    Date_of_Birth: Optional[str] = None
    Passport_Size_Photo: Optional[str] = None
    Passport_Number: Optional[str] = None
    Passport_Image: Optional[str] = None
    Passport_FieldNumber: Optional[str] = None
    UAN_Number: Optional[str] = None
    PAN_Number: Optional[str] = None
    PAN_Image: Optional[str] = None
    Aadhar_Number: Optional[str] = None
    Aadhar_Image: Optional[str] = None
    CurrentAddress_Street: Optional[str] = None
    CurrentAddress_City: Optional[str] = None
    CurrentAddress_State: Optional[str] = None
    CurrentAddress_PINcode: Optional[str] = None
    CurrentAddress_Country: Optional[str] = None
    PermanentAddress_Street: Optional[str] = None
    PermanentAddress_City: Optional[str] = None
    PermanentAddress_State: Optional[str] = None
    PermanentAddress_PINcode: Optional[str] = None
    PermanentAddress_Country: Optional[str] = None
    Educational_Details: Optional[Dict[str, Any]] = None
    Employment_Details: Optional[Dict[str, Any]] = None


class BritsUserBGVUpdateSchema(BaseModel):
    FirstName: Optional[str] = None
    LastName: Optional[str] = None
    MiddleName: Optional[str] = None
    FatherName: Optional[str] = None
    IsFresher: Optional[bool] = None
    IsUAN: Optional[bool] = None
    isPassport: Optional[bool] = None
    MobileNumber: Optional[str] = None
    Date_of_Birth: Optional[str] = None
    Marital_Status: Optional[str] = None
    Passport_Size_Photo: Optional[str] = None
    Passport_Number: Optional[str] = None
    Passport_Image: Optional[str] = None
    Passport_FieldNumber: Optional[str] = None
    UAN_Number: Optional[str] = None
    PAN_Number: Optional[str] = None
    PAN_Image: Optional[str] = None
    Aadhar_Number: Optional[str] = None
    Aadhar_Image: Optional[str] = None
    CurrentAddress_Street: Optional[str] = None
    CurrentAddress_City: Optional[str] = None
    CurrentAddress_State: Optional[str] = None
    CurrentAddress_PINcode: Optional[str] = None
    CurrentAddress_Country: Optional[str] = None
    PermanentAddress_Street: Optional[str] = None
    PermanentAddress_City: Optional[str] = None
    PermanentAddress_State: Optional[str] = None
    PermanentAddress_PINcode: Optional[str] = None
    PermanentAddress_Country: Optional[str] = None
    Educational_Details: Optional[Dict[str, Any]] = None
    Employment_Details: Optional[Dict[str, Any]] = None
    Selfie_Image: Optional[str] = None
    Ts_Trans_Id: Optional[str] = None

    class Config:
        from_attributes = True


class UploadSchema(BaseModel):
    Company_Portal_Url: str
    User_Id: str


def serialize_row(row):
    """ Convert a SQLAlchemy row to a serializable dictionary. """
    return {column: (value.isoformat() if isinstance(value, (date, datetime)) else value)
            for column, value in row._mapping.items()}


class DeleteTimeSheet(BaseModel):
    Company_Portal_Url: str
    TimeSheet_Ids: List[str]


class DeleteRequest(BaseModel):
    Company_Portal_Url: str
    Request_Ids: List[int]

class ProfileChangeRequest(BaseModel):
    RequestDetailType: str
    ChangeType: str
    UpdateField: Optional[str] = None
    UpdateValue: str
    DocumentURL: Optional[str] = None
class UpdateRequestSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    RequestType: Optional[str] = None
    RequestPriority: Optional[str] = None
    RequestDescription: Optional[str] = None
    startDate: Optional[List[datetime]] = None
    endDate: Optional[List[datetime]] = None
    Type: Optional[str] = None
    ProjectName: Optional[str] = None
    Task: Optional[str] = None
    Hours: Optional[List[float]] = None
    RequestAttachmentURL: Optional[str] = None
    ClientName: Optional[str] = None
    ProfileUpdate: Optional[ProfileChangeRequest] = None

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True


class TimeEntry(BaseModel):
    StartDate: datetime  # str
    EndDate: datetime  # str
    HoursWorked: float


class TimesheetData(BaseModel):
    Client_Name: str
    Project_Name: str
    SOW_Name: str
    Project_Task: str
    Notes: Optional[str]= None
    time: List[TimeEntry]


class TimesheetRequestData(BaseModel):
    Client_Name: str
    Project_Name: str
    Project_Task: str
    IPAddress: str
    Longitude: str
    Latitude: str
    time: List[TimeEntry]

class RequestSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    RequestType: Optional[str] = None
    RequestPriority: Optional[str] = None
    RequestDescription: Optional[str] = None
    startDate: Optional[List[datetime]] = None
    endDate: Optional[List[datetime]] = None
    Type: Optional[str] = None
    Hours: Optional[List[float]] = None
    RequestAttachmentURL: Optional[str] = None
    Timesheet: Optional[List[TimesheetRequestData]] = None
    ProfileUpdate: Optional[ProfileChangeRequest] = None


class TimesheetSchema(BaseModel):
    Company_Portal_Url: str
    User_Manager: Optional[str] = None
    Month: Optional[int] = None
    time_sheet_attachment_key: Optional[str] =None
    Timesheet: List[TimesheetData]
    IPAddress: Optional[str] = None
    Latitude: str
    Longitude: str
    Notes: Optional[str]=None


class GetTimesheet(BaseModel):
    Company_Portal_Url: str
    Month: str


class UpdateTimeSheet(BaseModel):
    Company_Portal_Url: str
    TimeSheetID: int
    Client_Name: str
    Project_Name: str
    SOW_Name: str
    User_Manager: str
    Project_Task: str
    Month: int
    time: List[TimeEntry]
    IPAddress: str
    Latitude: str
    Longitude: str
    time_sheet_attachment_key: str
    Notes: Optional[str]=None


class UpdatePassword(BaseModel):
    Company_Portal_Url: str
    old_password: str
    new_password: str


class ForgotPassword(BaseModel):
    Company_Portal_Url: str
    Email: str
    
class resendSchema(BaseModel):
    Company_Portal_Url: str
    email: str

class otpSchema(BaseModel):
    token: str
    email: str
    Company_Portal_Url: str
class TimesheetCountResponse(BaseModel):
    month: str
    count: int


class AdminTimesheet(BaseModel):
    Company_Portal_Url: str
    month: int
    year: int
    status : Optional[str] = None
    users: Optional[List[int]] = None
    filterBy: Optional[Dict[str, str]] = None


class UpdateTimesheet(BaseModel):
    Choice: str
    Company_Portal_Url: str
    ID: List[int]


class RequestStatusSchema(BaseModel):
    Choice: str
    Company_Portal_Url: str
    ID: List[int]


class timesheet(BaseModel):
    user_ids: list[int] = Field(
        default=None, description="Optional list of user IDs")
    Company_Portal_Url: str
    Day: Optional[str] = None
    Week: Optional[str] = None
    Month: Optional[str] = None


class Report(BaseModel):
    Company_Portal_Url: str
    StartDate: datetime
    EndDate: datetime
    users: list[int]


class TimeOffPolicySchema(BaseModel):
    Company_portal_Url: str
    Timeoff_Policy_Name: str
    Timeoff_Country: str
    TimeOff_Type: List[Dict[str, str | int]]
    Hours: Optional[int] = None
    Daily_Working_Hours: Optional[int] = None
    Monthly_Working_Hours: Optional[int] = None
    Yearly_Working_Hours: Optional[int] = None
    Yearly_Total_Hours: Optional[int] = None
    Paid_sick_days: Optional[int] = None
    Paid_sick_hours: Optional[int] = None
    Paid_timeoff_days: Optional[int] = None
    Paid_timeoff_hours: Optional[int] = None
    Unpaid_timeoff_days: Optional[int] = None
    Unpaid_timeoff_hours: Optional[int] = None
   
class HolidayDetail(BaseModel):
    Holiday_Date: str
    Holiday_Name: str
    Holiday_mandatory: bool


class HolidayScheme(BaseModel):
    Company_portal_Url: str
    Template_Name: str
    Template_Country: str
    Holiday_Details: List[HolidayDetail]

class ClientSchema(BaseModel):
    Company_Portal_Url: str
    ClientName: str
    ClientShortName: str
    ClientContactFirstname: str
    ClientContactLastname: str
    ClientContactEmail: str
    ClientContactPhoneNumber: str
    WebsiteURL: str
    ClientEIN: str
    ClientBillingContactFirstName: str
    ClientBillingContactLastName: str
    ClientBillingEmail: str
    ClientBillingPhoneNumber: str
    ClientBankName: str
    ClientBankAccountNumber: str
    ClientBankAddress: str
    ClientBankWireRoutingNumber: str
    ClientBankACHRoutingNumber: str
    logo_url: Optional[str] = None

class AdminTimesheet(BaseModel):
    Company_Portal_Url: str
    month: int
    year: int
    users: Optional[List[int]] = None
    group_by: str = 'week'
    status: Optional[str] = None
    own : Optional[int] = None
    filterBy: Optional[Dict[str, str]] = None
    
class ProjectSchema(BaseModel):
    Company_Portal_Url: str
    ProjectName: str
    ProjectStartDate: date
    ProjectEndDate: date
    ClientID: Optional[int] = None
    VendorID: Optional[int] = None
    PartnerID: Optional[int] = None
    ProjectTimesheetBuckets: Optional[List[str]] = Field(default_factory=list)
    image_url: Optional[str] = None  # Match database column name exactly
    
class SOWSchema(BaseModel):
    Company_Portal_Url: str
    SOWName: Optional[str] =None
    SOWBillableRate: Optional[float] = None
    ClientID: Optional[int] = None
    VendorID: Optional[int] = None
    PartnerID: Optional[int] = None
    ProjectID: Optional[int] = None
    ClientRepresentive: Optional[int] = None
    SOWAttachment: Optional[str] = None

class VendorSchema(BaseModel):
    Company_Portal_Url: str
    VendorName: str
    VendorManagerName: str
    VendorContactFirstName: str
    VendorContactLastName: str
    VendorContactEmail: str
    VendorContactPhoneNumber: str
    WebsiteURL: str
    ProjectAssigned: List[int]
    SOWAssigned: List[int]
    VendorEIN: str
    VendorBillingContactFirstName: str
    VendorBillingContactLastName: str
    VendorBillingEmail: str
    VendorBillingPhoneNumber: str
    VendorBankName: str
    VendorBankAccountNumber: str
    VendorBankAddress: str
    VendorBankWireRoutingNumber: str
    VendorBankACHRoutingNumber: str
    logo_url: Optional[str] = None
    
    
class DeleteUser(BaseModel):
    Company_Portal_Url: str
    User_ID: List[int]
    
class AssignClientSchema(BaseModel):
    Company_Portal_Url: str
    ClientID: List[int]
    ProjectID:List[int]
    UserID: int
    
class PartnerSchema(BaseModel):
    Company_Portal_Url: str
    PartnerName: str
    PartnerManagerName: str
    PartnerContactFirstname: str
    PartnerContactLastname: str
    PartnerContactEmail: str
    PartnerContactPhoneNumber: str
    WebsiteURL: str
    PartnerEIN: str
    PartnerBillingContactFirstName: str
    PartnerBillingContactLastName: str
    PartnerBillingEmail: str
    PartnerBillingPhoneNumber: str
    PartnerBankName: str
    PartnerBankAccountNumber: str
    PartnerBankAddress: str
    PartnerBankWireRoutingNumber: str
    PartnerBankACHRoutingNumber: str
    logo_url: Optional[str] = None
    
class FolderSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    FolderName: str
    EntityType: str
    ParentFolderID: Optional[int] = None
    
class FileSchema(BaseModel):
    Company_Portal_Url: Optional[str] = None
    FolderID: int
    FileName: str
    FileContent: str
    ContentType: str
    
class AddressVerify(BaseModel):
    Street: str
    city: str
    state: str
    pin: int
    country: str
    
    
class verification(BaseModel):
    First_Name: Optional[str] = None
    Last_Name: Optional[str] = None
    Date_of_Birth: Optional[date] = None
    UAN: Optional[str] = None
    Aadhar: Optional[int] = None
    passport: Optional[str] = None
    pan: Optional[str] = None
    Address: Optional[AddressVerify] = None
    
class bgvReportSchema(BaseModel):
    Company_Portal_Url: str
    User_ID: str
    data: Dict[str, Any]
    
class TimpolicySchema(BaseModel):
    Company_Portal_Url: str
    Timesheet_template: str
    Timesheet_week_day_start: str
    Timesheet_week_day_end: str
    Timesheet_restrict_hours: int
    Timesheet_week_time_end: time = Field(default=time(23, 59, 0))
    Timesheet_month_end_day: bool = Field(default=True)
    Timesheet_month_day_time: time = Field(default=time(23, 59, 0))
    Timesheet_month_rollover_days: int = 0
    Timesheet_fields: List  
    TimesheetClient: str
    
class SalarySplit(BaseModel):
    Company_Portal_Url: str
    UserUUID: Optional[str] = None
    Amount_CTC: Optional[float]
    Amount_PP_yearly: Optional[float]
    Amount_CAb_allowance_yearly: Optional[float]
    Amount_PF_Contribution_yearly: Optional[float]
    Amount_Salary_After_Deductions_yearly: Optional[float]
    Amount_Base_salary_yearly: Optional[float]
    Amount_HRA_yearly: Optional[float]
    Amount_Special_Allowances_yearly: Optional[float]
    Amount_LTA_yearly: Optional[float]
    Amount_Total_CTC_yearly: Optional[float]
    Amount_Compensation_Package_yearly: Optional[float]
    Amount_PP_Monthly: Optional[float]
    Amount_CAb_allowance_Monthly: Optional[float]
    Amount_PF_Contribution_Monthly: Optional[float]
    Amount_Salary_After_Deductions_Monthly: Optional[float]
    Amount_Base_salary_Monthly: Optional[float]
    Amount_HRA_Monthly: Optional[float]
    Amount_Special_Allowances_Monthly: Optional[float]
    Amount_LTA_Monthly: Optional[float]
    Amount_Total_CTC_Monthly: Optional[float]
    Amount_Compensation_Package_Monthly: Optional[float]
    
class SalarySchema(BaseModel):
    Company_Portal_Url: str
    UserUUID: Optional[str] = None
    Amount_CTC : Optional[float] = None
    
class UserReportSchema(BaseModel):
    Company_Portal_Url: str
    Useruuid: str
    
class violationSchema(BaseModel):
    Company_Portal_Url: str
    Useruuid: str
    violationType: str
    description: Optional[str] = None
    attachment: Optional[str] = None
    
    
class EmploymentHistorySchema(BaseModel):
    emp_name: str
    email: str
    sh_role: str
    job_role: str
    clients: List[str]
    projects: List[str]
    violations: List[str]
    remarks: str
    bgv_status: str

    class Config:
        from_attributes = True

class TenantNotificationSettings(BaseModel):
    timesheet_notification: bool
    request_notification: bool

    class Config:
        from_attributes = True


class UpdateNotification(BaseModel):
    notification_ids: List[int]
    read: bool