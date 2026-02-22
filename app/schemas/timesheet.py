"""Timesheet schemas."""

from datetime import datetime, time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TimeEntry(BaseModel):
    StartDate: datetime
    EndDate: datetime
    HoursWorked: float


class TimesheetData(BaseModel):
    Client_Name: str
    Project_Name: str
    SOW_Name: str
    Project_Task: str
    Notes: Optional[str] = None
    time: List[TimeEntry]


class TimesheetRequestData(BaseModel):
    Client_Name: str
    Project_Name: str
    Project_Task: str
    IPAddress: str
    Longitude: str
    Latitude: str
    time: List[TimeEntry]


class TimesheetSchema(BaseModel):
    Company_Portal_Url: str
    User_Manager: Optional[str] = None
    Month: Optional[int] = None
    time_sheet_attachment_key: Optional[str] = None
    Timesheet: List[TimesheetData]
    IPAddress: Optional[str] = None
    Latitude: str
    Longitude: str
    Notes: Optional[str] = None


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
    Notes: Optional[str] = None


class DeleteTimeSheet(BaseModel):
    Company_Portal_Url: str
    TimeSheet_Ids: List[str]


class TimesheetCountResponse(BaseModel):
    month: str
    count: int


class AdminTimesheet(BaseModel):
    Company_Portal_Url: str
    month: int
    year: int
    users: Optional[List[int]] = None
    group_by: str = "week"
    status: Optional[str] = None
    own: Optional[int] = None
    filterBy: Optional[Dict[str, str]] = None


class UpdateTimesheet(BaseModel):
    Choice: str
    Company_Portal_Url: str
    ID: List[int]


class timesheet(BaseModel):
    user_ids: list[int] = Field(default=None, description="Optional list of user IDs")
    Company_Portal_Url: str
    Day: Optional[str] = None
    Week: Optional[str] = None
    Month: Optional[str] = None


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
