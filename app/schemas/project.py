"""Project management schemas."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class ProjectSchema(BaseModel):
    Company_Portal_Url: str
    ProjectName: str
    ProjectStartDate: date
    ProjectEndDate: date
    ClientID: Optional[int] = None
    VendorID: Optional[int] = None
    PartnerID: Optional[int] = None
    ProjectTimesheetBuckets: Optional[List[str]] = Field(default_factory=list)
    image_url: Optional[str] = None
