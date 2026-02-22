from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from Models.db import schemas

from Models.db import models

class violation:
    def __init__(self, db:Session, company_portal_url):
        self.db = db
        self.company_portal_url = company_portal_url
        self.tenant = self._get_tenant_info()
        self.setuptables()
        
    def _get_tenant_info(self):
        user = (self.db.query(models.TenantInfo).filter(models.TenantInfo.PortalURL == self.company_portal_url).first())
        if user is None: raise HTTPException(status_code=404, detail={"message": "Schema not found"})
        return user
    
    def setuptables(self):
        self.usertable = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_user_info"
        self.violation = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_violations"
    
    def sql(self, type):
        query = {
            "insert-viol": f'''INSERT INTO {self.violation} ("UserUUID", "Violation_Type", "Violation_Description",\
                "Violation_Attachment_URL") VALUES (:uuid, :vtype, :vdesc, :vurl)''',
            "get-viol": f'''SELECT * FROM {self.violation} WHERE "UserUUID" = :uuid''',
        }
        return query[type]
    
    def execute(self, query, param, type):
        try:
            if type == "SELECT":
                return self.db.execute(text(query), param).mappings().all()
            elif type == "INSERT":
                self.db.execute(text(query), param)
                self.db.commit()
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Error occured: {e}")
        
    def add_violation(self, data: schemas.violationSchema):
        query = self.sql("insert-viol")
        params = {
            "uuid": data.Useruuid,
            "vtype": data.violationType,
            "vdesc": data.description,
            "vurl": data.attachment
        }
        self.execute(query, params, "INSERT")
        return True
    
    def get_violation(self, uuid):
        query = self.sql("get-viol")
        result = self.execute(query, {"uuid": uuid}, "SELECT")
        if result: return result
        else: return False