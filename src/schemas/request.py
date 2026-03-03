"""Request management schemas."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from src.schemas.timesheet import TimesheetRequestData


class ProfileChangeRequest(BaseModel):
    RequestDetailType: str
    ChangeType: str
    UpdateField: Optional[str] = None
    UpdateValue: str
    DocumentURL: Optional[str] = None


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


class DeleteRequest(BaseModel):
    Company_Portal_Url: str
    Request_Ids: List[int]


class RequestStatusSchema(BaseModel):
    Choice: str
    Company_Portal_Url: str
    ID: List[int]


class Report(BaseModel):
    Company_Portal_Url: str
    StartDate: datetime
    EndDate: datetime
    users: list[int]
