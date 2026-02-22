from sqlalchemy.orm import Session
from logging import Logger
from Models.db import models
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()

class TenantSettingsManager:
    def __init__(self, db: Session, Company_Portal_Url: str = None, logger: Logger = None):
        self.db = db
        self.logger = logger
        if Company_Portal_Url:
            self.company_portal_url = Company_Portal_Url
            self.tenant =self._get_tenant_info()
            self.setuptables()
        
    def _get_tenant_info(self):
        user = (self.db.query(models.TenantInfo).filter(models.TenantInfo.PortalURL == self.company_portal_url).first())
        if user is None: return error.error("Schema not found", 404, "Schema")
        return user
    
    def setuptables(self):
        self.tenant_settings_table = f"{self.tenant.SchemaName}.tb_{self.tenant.ShortName}_tenant_settings"
        print("self.tenant_settings_table",self.tenant_settings_table)
    
    async def is_request_notification_enabled(self) -> bool:
        try:
            query = text(f"""
                SELECT "request_notification"
                FROM {self.tenant_settings_table}
                WHERE "TenantUUID" = :tenant_uuid
            """)

            result = self.db.execute(query, {"tenant_uuid": self.tenant.TenantUUID})
            print("result",result)
            row = result.fetchone()
            print("row",row)

            if row:
                return row[0]  # True or False
            else:
                return False  # Default to False if not found
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error checking request notification setting: {str(e)}")
            raise e
    

    async def is_timesheet_notification_enabled(self) -> bool:
        try:
            query = text(f"""
                SELECT "timesheet_notification"
                FROM {self.tenant_settings_table}
                WHERE "TenantUUID" = :tenant_uuid
            """)

            result = self.db.execute(query, {"tenant_uuid": self.tenant.TenantUUID})
            row = result.fetchone()

            if row:
                return row[0]  # True or False
            else:
                return False  # Default to False if not found
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error checking timesheet notification setting: {str(e)}")
            raise e
    
    async def update_notification_settings(self, timesheet_notification: bool, request_notification: bool):
        try:
            query = text(f"""
                UPDATE {self.tenant_settings_table}
                SET 
                    "timesheet_notification" = :timesheet_notification,
                    "request_notification" = :request_notification,
                    "UpdatedTimeAndDate" = CURRENT_TIMESTAMP
                WHERE "TenantUUID" = :tenant_uuid
                RETURNING 
                    "timesheet_notification", 
                    "request_notification";
            """)

            result = self.db.execute(query, {
                "timesheet_notification": timesheet_notification,
                "request_notification": request_notification,
                "tenant_uuid": self.tenant.TenantUUID
            })
            self.db.commit()

            updated_row = result.fetchone()

            if updated_row:
                # Fetch the updated values
                updated_timesheet, updated_request = updated_row

                # Build a custom response message
                messages = []
                if updated_timesheet:
                    messages.append("Timesheet notifications turned ON")
                else:
                    messages.append("Timesheet notifications turned OFF")
                
                if updated_request:
                    messages.append("Request notifications turned ON")
                else:
                    messages.append("Request notifications turned OFF")

                final_message = " | ".join(messages)

                return {
                    "message": final_message
                }
            else:
                return error.error("Tenant settings not found", 404, "Tenant Settings")
        except Exception as e:
            print("Exception:", str(e))
            raise e
            


        
            
            
        