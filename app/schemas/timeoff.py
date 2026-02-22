"""Time-off and holiday policy schemas."""

from typing import Dict, List, Optional

from pydantic import BaseModel


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
