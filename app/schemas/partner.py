"""Partner management schemas."""

from typing import Optional

from pydantic import BaseModel


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
