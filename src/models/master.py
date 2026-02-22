"""
Master schema ORM models (db_saciahub_sch_master).
"""

import random
import string
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.database import Base


class TenantInfo(Base):
    __tablename__ = "sch_master_tb_tenant_info"
    __table_args__ = {"schema": "db_saciahub_sch_master"}

    TABLEUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    ID = Column(BigInteger, primary_key=True, index=True)
    TenantUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    TenantName = Column(String(255), nullable=False)
    ShortName = Column(String(50))
    SchemaName = Column(String(255), nullable=False)
    PortalURL = Column(String(255))
    TenantDetails = Column(JSON, nullable=True)
    ContactName = Column(String(255))
    ContactEmail = Column(String(255))
    ContactPhoneNumber = Column(String(20))
    BillingContactName = Column(String(255), nullable=True)
    BillingContactEmail = Column(String(255), nullable=True)
    BillingContactPhoneNumber = Column(String(20), nullable=True)
    BillingAddressStreetName = Column(String(255), nullable=True)
    BillingAddressCity = Column(String(100), nullable=True)
    BillingAddressState = Column(String(100), nullable=True)
    BillingAddressCountry = Column(String(100), nullable=True)
    BillingAddressZipcode = Column(String(20), nullable=True)
    Licenses = Column(JSON, nullable=True)
    ActiveModules = Column(JSON, nullable=True)
    CreationTimeAndDate = Column(DateTime, default=func.now())
    UpdatedTimeAndDate = Column(DateTime, default=func.now(), onupdate=func.now())
    FieldsUpdated = Column(JSON, nullable=True)
    FieldsValuesUpdated = Column(JSON, nullable=True)
    TenantStatus = Column(String(255), nullable=True)
    Timesheets_Templates = Column(JSON, nullable=True)


class UserBgv(Base):
    __tablename__ = "tb_master_exd_bgvinfo"
    __table_args__ = {"schema": "db_saciahub_sch_master"}

    TABLEUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    ID = Column(Integer, primary_key=True, index=True)
    UserUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    PAN_Verification = Column(JSONB)
    Aadhar_Verification = Column(JSONB)
    Passport_Verification = Column(JSONB)
    UAN_Verification = Column(JSONB)
    Mobile_to_UAN = Column(JSONB)
    First_Name = Column(String)
    Last_Name = Column(String)
    Middle_Name = Column(String)
    Father_Name = Column(String)
    IsFresher = Column(Boolean)
    IsUAN = Column(Boolean)
    isPassport = Column(Boolean)
    Mobile_Number = Column(String)
    Marital_Status = Column(String)
    Date_of_Birth = Column(String)
    Passport_Size_Photo_URL = Column(String)
    Passport_Number = Column(String)
    Passport_FileNumber = Column(String)
    Passport_Image_URL = Column(String)
    UAN_Number = Column(String)
    PAN_Number = Column(String)
    PAN_Image_URL = Column(String)
    Aadhar_Number = Column(String)
    Aadhar_Image_URL = Column(String)
    CurrentAddress_Street = Column(String)
    CurrentAddress_City = Column(String)
    CurrentAddress_State = Column(String)
    CurrentAddress_PINcode = Column(String)
    CurrentAddress_Country = Column(String)
    PermanentAddress_Street = Column(String)
    PermanentAddress_City = Column(String)
    PermanentAddress_State = Column(String)
    PermanentAddress_PINcode = Column(String)
    PermanentAddress_Country = Column(String)
    Educational_Details = Column(JSONB)
    Employment_Details = Column(JSONB)
    Criminal_check_Results = Column(JSONB)
    Created_date = Column(DateTime, default=func.now())


class UserViolation(Base):
    __tablename__ = "tb_master_exd_violation_info"
    __table_args__ = {"schema": "db_saciahub_sch_master"}

    TABLEUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    ID = Column(Integer, primary_key=True, index=True)
    User_Id = Column(String)
    Violation_Type = Column(String, nullable=True)
    Violation_Description = Column(String, nullable=True)
    Violation_Attachment_URL = Column(String, nullable=True)
    Reported_Company = Column(String)
    Reported_User = Column(String)
    Created_date = Column(DateTime, default=func.now())


class HolidayTemplate(Base):
    __tablename__ = "sch_master_tb_holiday_template"
    __table_args__ = {"schema": "db_saciahub_sch_master"}

    TABLEUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    ID = Column(Integer, primary_key=True, index=True)
    Template_Name = Column(String)
    Template_Country = Column(String)
    Holiday_Details = Column(JSONB)


class TimeoffPolicy(Base):
    __tablename__ = "sch_master_tb_timeoff_policy"
    __table_args__ = {"schema": "db_saciahub_sch_master"}

    TABLEUUID = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)
    ID = Column(Integer, primary_key=True, index=True)
    Timeoff_Policy_Name = Column(String)
    Timeoff_Country = Column(String)
    Daily_Working_Hours = Column(Integer)
    Monthly_Working_Hours = Column(Integer)
    Yearly_Working_Hours = Column(Integer)
    Yearly_Total_Hours = Column(Integer)
    Timeoff_Details = Column(JSONB)


def generate_user_id() -> str:
    """Generate a random 6-character alphanumeric ID."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(6))
