"""Vendor management schemas."""

from typing import List, Optional

from pydantic import BaseModel


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
