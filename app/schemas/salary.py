"""Salary schemas."""

from typing import Optional

from pydantic import BaseModel


class SalarySplit(BaseModel):
    Company_Portal_Url: str
    UserUUID: Optional[str] = None
    Amount_CTC: Optional[float] = None
    Amount_PP_yearly: Optional[float] = None
    Amount_CAb_allowance_yearly: Optional[float] = None
    Amount_PF_Contribution_yearly: Optional[float] = None
    Amount_Salary_After_Deductions_yearly: Optional[float] = None
    Amount_Base_salary_yearly: Optional[float] = None
    Amount_HRA_yearly: Optional[float] = None
    Amount_Special_Allowances_yearly: Optional[float] = None
    Amount_LTA_yearly: Optional[float] = None
    Amount_Total_CTC_yearly: Optional[float] = None
    Amount_Compensation_Package_yearly: Optional[float] = None
    Amount_PP_Monthly: Optional[float] = None
    Amount_CAb_allowance_Monthly: Optional[float] = None
    Amount_PF_Contribution_Monthly: Optional[float] = None
    Amount_Salary_After_Deductions_Monthly: Optional[float] = None
    Amount_Base_salary_Monthly: Optional[float] = None
    Amount_HRA_Monthly: Optional[float] = None
    Amount_Special_Allowances_Monthly: Optional[float] = None
    Amount_LTA_Monthly: Optional[float] = None
    Amount_Total_CTC_Monthly: Optional[float] = None
    Amount_Compensation_Package_Monthly: Optional[float] = None


class SalarySchema(BaseModel):
    Company_Portal_Url: str
    UserUUID: Optional[str] = None
    Amount_CTC: Optional[float] = None
