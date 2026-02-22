"""Tenant/Company schemas."""

from pydantic import BaseModel


class CustomerSchema(BaseModel):
    Company_Name: str
    Contact_FirstName: str
    Contact_LastName: str
    Contact_Email: str
    Contact_PhoneNumber: str
    Company_ShortName: str

    class Config:
        from_attributes = True
