"""BGV (Background Verification) schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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
    isPassport: Optional[bool] = None
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


class bgvReportSchema(BaseModel):
    Company_Portal_Url: str
    User_ID: str
    data: Dict[str, Any]


class AddressVerify(BaseModel):
    Street: str
    city: str
    state: str
    pin: int
    country: str


class verification(BaseModel):
    First_Name: Optional[str] = None
    Last_Name: Optional[str] = None
    Date_of_Birth: Optional["date"] = None
    UAN: Optional[str] = None
    Aadhar: Optional[int] = None
    passport: Optional[str] = None
    pan: Optional[str] = None
    Address: Optional[AddressVerify] = None


# Avoid circular import for date
from datetime import date  # noqa: E402
