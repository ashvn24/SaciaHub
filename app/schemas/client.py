"""Client management schemas."""

from typing import Optional

from pydantic import BaseModel


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
