from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from Models.db.schemas import SalarySplit
from App.Models.Classes.GetUser import GetUser
from Models.db import models
import logging
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)


class SalaryManager:
    def __init__(self, db: Session, Company_Portal_Url, token_info):
        self.db = db
        self.Company_Portal_Url =  Company_Portal_Url
        self.token_info = token_info
        self.is_admin = self._is_admin(token_info)
        self.customer = self.get_tenant_info(Company_Portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.setup_salary_table()
        GetUser(self.db, Company_Portal_Url).verify_user(token_info)
        
    def _is_admin(self, token_info):
        if "role" not in token_info or token_info["role"] not in ["Admin", "Manager", "HR"]:
            return error.error("Admin privileges required", 403, "Admin privileges required")
        return True
    
    def get_tenant_info(self, company_portal_url: str):
        self.Company_Portal_Url = company_portal_url
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        print(user.TenantUUID)
        self.customer = user
        if user is None:
            return error.error("Schema not found", 404, "Schema not found")
        return user
    
    def setup_salary_table(self):
        self.user_table = f"{self.schema_name}.tb_{self.short_name}_user_info"
        self.salaryTable = f"{self.schema_name}.tb_{self.short_name}_salary_split"
        self.salary_deductions_table = f"{self.schema_name}.tb_{self.short_name}_salary_deductions"
        self._salary_compensations_table = f"{self.schema_name}.tb_{self.short_name}_salary_compensations"
        
    def getprefixedData(self, tenant_uuid):
        
        query_deductions = text(f'SELECT * FROM {self.salary_deductions_table} WHERE "TenantUUID" = :tenant_uuid')
        query_compensations = text(f'SELECT * FROM {self._salary_compensations_table} WHERE "TenantUUID" = :tenant_uuid')

        deductions = self.db.execute(query_deductions, {"tenant_uuid": tenant_uuid}).mappings().one_or_none()
        compensations = self.db.execute(query_compensations, {"tenant_uuid": tenant_uuid}).mappings().one_or_none()

        # Optionally, you can merge and process the data in Python
        return deductions, compensations
        
    async def getsalarySplit(self, ctc):
        try:
            deductions, compensations = self.getprefixedData(self.customer.TenantUUID)

            totalDeduc = deductions["Amount_PP"] + deductions["Amount_PF_Contribution"] + deductions["Amount_CAb_allowance"]
            Salary = ctc - totalDeduc
            base = (compensations["Amount_Base_salary"])/100
            hra = (compensations["Amount_HRA"])/100
            spl = (compensations["Amount_Special_Allowances"])/100
            lta = (compensations["Amount_LTA"])/100
            ylta = lta* Salary
            yspl = spl * Salary
            yhra =hra * Salary
            ybase = base* Salary
            SalarySplit = {
                "PP": deductions["Amount_PP"],
                "Cab": deductions["Amount_CAb_allowance"],
                "PF": deductions["Amount_PF_Contribution"],
                "Salary": Salary,
                "BaseSalary": base,
                "HRA": hra,
                "Special": spl,
                "LTA": lta,
                "Yearly_PP": deductions["Amount_PP"],
                "Yearly_Cab": deductions["Amount_CAb_allowance"],
                "Yearly_PF": deductions["Amount_PF_Contribution"],
                "Yearly_BaseSalary": ybase,
                "Yearly_HRA": hra * Salary,
                "Yearly_Special": yspl,
                "Yearly_LTA": ylta,
                "Monthly_PP": (deductions["Amount_PP"])/12,
                "Monthly_Cab": (deductions["Amount_CAb_allowance"])/12,
                "Monthly_PF": (deductions["Amount_PF_Contribution"])/12,
                "Monthly_BaseSalary": ybase/12,
                "Monthly_HRA": yhra/12,
                "Monthly_Special": yspl/12,
                "Monthly_LTA": ylta/12,
                "Total": ctc,
                "TotalCTCAmt": ctc,
                "TotalCompensationPackage": ctc-yspl,
            }
            return SalarySplit
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            raise e
    
    async def createSalarySplit(self, data: SalarySplit):
        try:
            SalData = data.dict()
            SalData.pop('Company_Portal_Url')
                        
            columns = ", ".join([f'"{k}"' for k in SalData.keys()])
            values = ", ".join([f':{k}' for k in SalData.keys()])
            
            insert_query = text(f'''
                INSERT INTO {self.salaryTable} ({columns})
                VALUES ({values})
            ''')
            
            self.db.execute(insert_query, SalData)
            self.db.commit()
            
            return JSONResponse(
                status_code=201,
                content={"message": "SalarySplit created successfully"}
            )
            
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            raise e