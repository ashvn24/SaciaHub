from fastapi import HTTPException
from sqlalchemy import text
from Models.db import models
from sqlalchemy.orm import Session



class token:
    def __init__(self, db:Session, company_portal_url):
        self.db = db
        self.company_portal_url = company_portal_url
        self.tenant = self._get_tenant_info()
        self.setuptables()
        
    def setuptables(self):
        self.user_table = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_user_info"
        
    def getquery(self, type):
        query = {
            "get-user": f'''SELECT * FROM {self.user_table} WHERE "UserUUID" = :useruuid''',
            "update-token": f'''UPDATE {self.user_table} SET "authtoken" = :token WHERE "UserUUID" = :useruuid''',
        }
        return query[type]
    
    def execute(self, query, params, type):
        try:
            if type == "SELECT":
                return self.db.execute(text(query), params).mappings().all()
            elif type == "UPDATE":
                self.db.execute(text(query), params)
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            print(f"Error logging API call: {str(e)}")
            
    def _get_tenant_info(self):
        user = (self.db.query(models.TenantInfo).filter(models.TenantInfo.PortalURL == self.company_portal_url).first())
        print("\nuser", user, self.company_portal_url)
        if user is None: raise HTTPException(status_code=404, detail={"message": "Schema not found"})
        return user
    
    def getuserdetails(self, uuid):
        query = self.getquery("get-user")
        result = self.execute(query, {"useruuid": uuid}, "SELECT")
        if not result:
            raise HTTPException(status_code=404, detail={"message": "User not found"})
        return result[0]
        
    def updatetoken(self, uuid, token):
        query = self.getquery("update-token")
        self.execute(query, {"useruuid": uuid, "token": token}, "UPDATE")
        # self.db.commit()
        
    def checktoken(self, uuid):
        user = self.getuserdetails(uuid)
        # print("User Details:", user,"\n")
        print("User Auth Token:", user["authtoken"])
        if user and user["authtoken"] is None:
            print("Invalid Token")
            raise HTTPException(status_code=400, detail="invalid token")