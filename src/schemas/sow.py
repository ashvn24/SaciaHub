"""SOW (Statement of Work) schemas."""

from typing import Optional

from pydantic import BaseModel


class SOWSchema(BaseModel):
    Company_Portal_Url: str
    SOWName: Optional[str] = None
    SOWBillableRate: Optional[float] = None
    ClientID: Optional[int] = None
    VendorID: Optional[int] = None
    PartnerID: Optional[int] = None
    ProjectID: Optional[int] = None
    ClientRepresentive: Optional[int] = None
    SOWAttachment: Optional[str] = None
