import json
from typing import Any, Dict, List
from fastapi import HTTPException
from sqlalchemy import UUID, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError


class TimesheetDetails:
    def __init__(self, user, db: Session):
        self.db = db
        self.shortname = user.ShortName
        self.schema = user.SchemaName
        self.user_table = self._get_user_table()
        self.project_table = self._get_project_table()
        self.sow_table = self._get_sow_table()

    def _get_user_table(self):
        return f"{self.schema}.tb_{self.shortname}_user_info"

    def _get_project_table(self):
        return f"{self.schema}.tb_{self.shortname}_project_info"

    def _get_sow_table(self):
        return f"{self.schema}.tb_{self.shortname}_sow_info"

    def get_timesheet_details(self, user_uuid: UUID) -> Dict[str, List[Dict[str, Any]]]:         
        try:
            # Fetch user SOW query - use parameterized query for UUID
            user_sow_query = text(f"""
                SELECT "SOW"
                FROM {self.user_table}
                WHERE "UserUUID" = :user_uuid
            """)
            
            # Execute with UUID converted to string
            user_sow_result = self.db.execute(
                user_sow_query, {"user_uuid": str(user_uuid)}
            ).fetchone()
            
            if not user_sow_result or not user_sow_result[0]:
                return None
            
            # Ensure sow_names is a list of strings
            sow_names = user_sow_result[0] if isinstance(user_sow_result[0], list) else [user_sow_result[0]]
            
            if not sow_names:
                return None
            print(sow_names)
            # Modify the project details query to use UUID casting
            project_details_query = text(f"""
                SELECT
                    p."ClientName",
                    p."ClientUUID",
                    ps."ProjectUUID",
                    ps."ProjectName",
                    p."ProjectTimesheetBuckets",
                    ps."SOWName",
                    ps."SOWUUID"
                FROM {self.sow_table} ps
                JOIN {self.project_table} p ON ps."ProjectUUID" = p."ProjectUUID"
                WHERE ps."SOWUUID"::uuid = ANY(CAST(:sow_names AS uuid[]))
            """)
            
            # Execute with the list of SOW names 
            project_details_result = self.db.execute(
                project_details_query, {"sow_names": sow_names}
            ).fetchall()
            print(project_details_result)
            # Rest of the method remains the same...
            timesheet_details = []
            for detail in project_details_result:
                client_name ={"name": detail[0], "ID":str(detail[1])}
                project_name = {"name":detail[3], "ID": str(detail[2])}
                activities = detail[4] if detail[4] else {}
                sow_name = {"name": detail[5], "ID": str(detail[6])}
                
                client = next(
                    (c for c in timesheet_details if c["client"] == client_name), None)
                if client:
                    client["projects"].append({
                        "name": project_name,
                        "sow": sow_name,
                        "activities": activities
                    })
                else:
                    timesheet_details.append({
                        "client": client_name,
                        "projects": [{
                            "name": project_name,
                            "sow": sow_name,
                            "activities": activities
                        }]
                    })
            
            return timesheet_details
        
        except Exception as e:
            print(f"Database error: {e}")
            raise
