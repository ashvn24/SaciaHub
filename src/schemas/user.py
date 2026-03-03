"""User management schemas."""

from typing import List, Optional

from pydantic import BaseModel


class BritsUserSchema(BaseModel):
    Company_Portal_Url: str
    LastName: str
    FirstName: str
    User_Email: str
    User_role: Optional[str] = None
    Job_Role: Optional[str] = None
    module: List[str] = []
    Manager: Optional[int] = None
    HR_Manager: Optional[int] = None
    Team: str

    class Config:
        from_attributes = True


class DeleteUser(BaseModel):
    Company_Portal_Url: str
    User_ID: List[int]


class AssignClientSchema(BaseModel):
    Company_Portal_Url: str
    ClientID: List[int]
    ProjectID: List[int]
    UserID: int


class UserReportSchema(BaseModel):
    Company_Portal_Url: str
    Useruuid: str


class EmploymentHistorySchema(BaseModel):
    emp_name: str
    email: str
    sh_role: str
    job_role: str
    clients: List[str]
    projects: List[str]
    violations: List[str]
    remarks: str
    bgv_status: str

    class Config:
        from_attributes = True
