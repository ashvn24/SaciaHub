from typing import Dict, List
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from datetime import datetime
import logging
from dateutil.relativedelta import relativedelta
from Models.Classes.GetUser import GetUser
from Models.Classes.TimesheetManager import ViewTimeSheetManager
from Models.utils.dashboard import fetch_timesheets, request_dashboard
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

from Models.db import models
logger = logging.getLogger(__name__)


class RequestCountsService:
    def __init__(self, db: Session, token_info: dict, company_portal_url: str):
        self.db = db
        self.token_info = token_info
        self.company_portal_url = company_portal_url
        self.user = self._get_user()
        self.schema_name = self.user.SchemaName
        self.request_table = f"tb_{self.user.ShortName}_requests"
        self.timesheet_table = f"tb_{self.user.ShortName}_timesheet"
        self.time_sheet_table = f"{self.schema_name}.{self.timesheet_table}"
        self.request_sheet_table = f"{self.schema_name}.{self.request_table}"
        GetUser(self.db, company_portal_url).verify_user(token_info)
        
    def _get_user(self):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if not user:
            return error.error("User not found", 404, "User Not Found")
        return user

    def get_request_counts(self, day: str = None, week: str = None, month: str = None, type: str = None):
        try:
            print("her1")
            current_date = datetime.now()
            current_month = current_date.strftime("%m")
            current_year = current_date.year

            print("her1")
            query = self._build_query()
            result = self.db.execute(
                query,
                {
                    "UserUUID": self.token_info["Id"],
                    "current_month": current_month,
                    "current_year": current_year,
                    "short_name": self.user.ShortName
                },
            ).fetchone()

            if not result:
                return self._get_empty_result()

            hours_to = self.token_info.get("hours", 12)
            return self._format_result(result, hours_to, day, week, month, type)

        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(sql_exc)}")
            raise sql_exc
        except Exception as e:
            raise e

    def _build_query(self):
        time_sheet_table = f"{self.schema_name}.{self.timesheet_table}"
        request_sheet_table = f"{self.schema_name}.{self.request_table}"

        print("her1")
        return text(
            f"""
            WITH request_counts AS (
            SELECT
                COUNT(*) as total_count,
                COUNT(CASE WHEN "RequestStatus" = 'Approved' THEN 1 END) as approved_count,
                COUNT(CASE WHEN "RequestStatus" = 'Pending' THEN 1 END) as pending_count,
                COUNT(CASE WHEN "RequestStatus" = 'Denied' THEN 1 END) as denied_count,
                SUM(CASE
                    WHEN "RequestStatus" = 'Approved' AND "RequestType" = 'TimeOff' THEN
                        CAST(("RequestDetails"->>'Hours') AS DECIMAL)
                    ELSE 0
                END) as accepted_timeoff_count,
                COUNT(CASE WHEN "RequestType" = 'TimeSheet' THEN 1 END) as timesheet_count
                FROM {self.request_sheet_table}
                WHERE "UserUUID" = :UserUUID
            ),
            current_month_timesheet_counts AS (
                SELECT
                    COUNT(*) as current_month_timesheet_count,
                    COUNT(CASE WHEN "Status" = 'Approved' THEN 1 END) as current_month_approved_timesheet_count,
                    COUNT(CASE WHEN "Status" = 'Pending' THEN 1 END) as current_month_pending_timesheet_count,
                    COUNT(CASE WHEN "Status" = 'Denied' THEN 1 END) as current_month_denied_timesheet_count
                FROM {self.time_sheet_table}
                WHERE "UserUUID" = :UserUUID
                  AND EXTRACT(MONTH FROM "Date") = :current_month
                  AND EXTRACT(YEAR FROM "Date") = :current_year
                  AND "ClientName" != :short_name
            ),
                timesheet_hours AS (
            SELECT
                SUM(total_hours) as total_hours
            FROM (
                SELECT
                    (json_array_elements("RequestDetails"->'Time')->>'Hours')::FLOAT as total_hours
                FROM {self.request_sheet_table}
                WHERE "RequestType" = 'TimeSheet'
                AND "UserUUID" = :UserUUID
            ) subquery
                    )
            SELECT *
                FROM request_counts, current_month_timesheet_counts, timesheet_hours
        """
        )

    def _get_empty_result(self):
        return {
            "total_count": 0,
            "approved_count": 0,
            "pending_count": 0,
            "denied_count": 0,
            "accepted_timeoff_count": 0,
            "timesheet_count": 0,
            "total_timesheet_hours": 0,
            "current_month_timesheet_count": 0,
            "current_month_approved_timesheet_count": 0,
            "current_month_pending_timesheet_count": 0,
            "current_month_denied_timesheet_count": 0,
            "last_3_timesheets": [],
            "last_3_requests": [],
            "last_payDay":""
        }

    def _format_result(self, result, hours_to, day, week, month, type):
        print("here")
        total_to = 18 * hours_to
        accepted_timeoff_count = result.accepted_timeoff_count or 0
        to_left = (total_to - accepted_timeoff_count) / hours_to
        to_taken = accepted_timeoff_count / hours_to
        to_left_rounded = round(to_left, 1)
        to_taken_rounded = round(to_taken, 1)
        previous_month = (datetime.now() - relativedelta(months=1)).strftime('%B')
        print("here")
        return {
            "Request": {
                "total_count": result.total_count,
                "approved_count": result.approved_count,
                "pending_count": result.pending_count,
                "denied_count": result.denied_count,
            },
            "TimeOff": {
                "Used_timeoff_count": to_taken_rounded,
                "Available_timeoff_count": to_left_rounded,
            },
            "MissedTimesheet": {
                "timesheet_count": result.timesheet_count,
                "total_timesheet_hours": result.total_hours or 0,
            },
            "current_month_timesheet": {
                "current_month_timesheet_count": result.current_month_timesheet_count,
                "current_month_approved_timesheet_count": result.current_month_approved_timesheet_count,
                "current_month_pending_timesheet_count": result.current_month_pending_timesheet_count,
                "current_month_denied_timesheet_count": result.current_month_denied_timesheet_count,
            },
            "last_3_timesheets": fetch_timesheets(
                self.db, self.time_sheet_table, self.token_info, day, week, month, self.company_portal_url
            ),
            "last_3_requests": request_dashboard(
                self.db, self.request_sheet_table, self.token_info, type
            ),
            "last_payDay": f"5 {previous_month}"
        }
        
class TimesheetCountResponse(BaseModel):
    month: str
    count: int
class TimesheetCountService:
    def __init__(self, db: Session, token_info: Dict, company_portal_url: str):
        self.db = db
        self.token_info = token_info
        self.company_portal_url = company_portal_url
        self.user = self._get_user()
        self.time_sheet_table = f"{self.user.SchemaName}.tb_{self.user.ShortName}_timesheet"
        self.is_admin = self._check_admin_role()

    def _get_user(self):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user

    def _check_admin_role(self):
        return True if self.token_info['role'] == 'Admin' else False

    def get_timesheet_counts(self, year: int = None) -> List[TimesheetCountResponse]:
        try:
            current_date = datetime.now()
            current_year = current_date.year
            current_month = current_date.month

            year = year or current_year
            end_month = 12 if year < current_year else current_month

            query = self._build_query()
            params = {"year": year, "end_month": end_month, "short_name": self.user.ShortName}
            
            # if not self.is_admin:
            params["user_uuid"] = self.token_info["Id"]

            result = self.db.execute(query, params)

            counts = [
                TimesheetCountResponse(month=row.month, count=row.count) for row in result
            ]

            return self._fill_missing_months(counts, year, end_month)

        except Exception as e:
            raise e

    def _build_query(self):
        base_query = f"""
            SELECT
                TO_CHAR(DATE_TRUNC('month', "Date"), 'YYYY-MM') as month,
                COUNT(DISTINCT "TimesheetUUID") as count
            FROM {self.time_sheet_table}
            WHERE
                EXTRACT(YEAR FROM "Date") = :year AND
                EXTRACT(MONTH FROM "Date") <= :end_month 
                AND ("ClientName" != :short_name OR "ProjectBucket" = 'Time Off')
        """
        
        # if not self.is_admin:
        base_query += " AND \"UserUUID\" = :user_uuid"
        
        base_query += """
            GROUP BY DATE_TRUNC('month', "Date")
            ORDER BY month DESC
        """
        
        return text(base_query)

    def _fill_missing_months(self, counts: List[TimesheetCountResponse], year: int, end_month: int) -> List[TimesheetCountResponse]:
        all_months = [f"{year}-{month:02d}" for month in range(1, end_month + 1)]
        counts_dict = {count.month: count.count for count in counts}

        final_counts = [
            TimesheetCountResponse(
                month=datetime.strptime(month, "%Y-%m").strftime("%B %Y"),
                count=counts_dict.get(month, 0),
            )
            for month in all_months
        ]

        return list(reversed(final_counts))
    
    
class ManagerDashboardExtension(ViewTimeSheetManager):
    def __init__(self, db: Session, company_portal_url: str, token_info: Dict):
        try:
            super().__init__(db, company_portal_url, token_info)
            if self.token_info["role"] != "Manager":
                return error.error("Unauthorized access", 403, "Unauthorized access")
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise e

    def _get_tenant_info(self):
        print("here", self.company_portal_url)
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user

    def get_manager_dashboard_data(self) -> Dict:
        try:
            print("here")
            return {
                "timesheet_status_counts": self.get_timesheet_status_counts(),
                "last_five_timesheets": self.get_last_five_timesheets(),
                "request_data": self.requestdata()
            }
        except Exception as e:
            raise e
        
    def requestdata(self):
        try:
            query = f"""
            SELECT 
                COUNT(*) AS total_pending_requests, 
                SUM(CASE WHEN r."RequestType" = 'HR' THEN 1 ELSE 0 END) AS hr_requests,
                SUM(CASE WHEN r."RequestType" = 'Access' THEN 1 ELSE 0 END) AS access_requests,
                SUM(CASE WHEN r."RequestType" = 'TimeOff' THEN 1 ELSE 0 END) AS timeoff_requests,
                SUM(CASE WHEN r."RequestType" = 'ProfileChange' THEN 1 ELSE 0 END) AS profile_change_requests
            FROM {self.db_helper.reqtb} AS r
            LEFT JOIN {self.db_helper.user_table} AS u ON r."UserUUID" = u."UserUUID"  -- Fixing JOIN syntax
            WHERE r."RequestStatus" = 'Pending' AND u."User_manager" = :uuid
            """

            result = self.db.execute(text(query), {"uuid": self.token_info["Id"]}).fetchone()


            return {
                "total_pending_requests": result.total_pending_requests or 0,
                "hr_requests": result.hr_requests or 0,
                "access_requests": result.access_requests or 0,
                "timeoff_requests": result.timeoff_requests or 0,
                "profile_change_requests": result.profile_change_requests or 0,
            }
        except Exception as e:
            raise e


    def get_timesheet_status_counts(self) -> Dict[str, int]:
        try:
            print("here")
            query = f"""
            SELECT 
                SUM(CASE WHEN ts."Status" = 'Pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN ts."Status" = 'Approved' THEN 1 ELSE 0 END) as approved_count,
                SUM(CASE WHEN ts."Status" = 'Denied' THEN 1 ELSE 0 END) as denied_count
            FROM {self.db_helper.time_sheet_table} ts
            JOIN {self.db_helper.user_table} ui ON ts."UserUUID" = ui."UserUUID"
            WHERE ui."User_manager" = :manager_uuid
            """
            params = {"manager_uuid": self.token_info["Id"]}
            result = self.db_helper.execute_query(query, params)
            print(result,"-----")
            if result:
                return {
                    "Queue": result[0]["pending_count"] or 0,
                    "Processed": result[0]["approved_count"] or 0,
                    "Denied": result[0]["denied_count"] or 0
                }
            return {"Pending": 0, "Approved": 0, "Denied": 0}
        except Exception as e:
            raise e

    def get_last_five_timesheets(self) -> List[Dict]:
        try:
            query = f"""
            SELECT 
                ts."ID", ts."TIMN", ts."TIMD", ts."UserUUID", ts."ClientName", ts."ProjectName",
                ts."SOWName", ts."ProjectBucket", ts."Date", ts."HoursWorked", ts."Status",
                ui."FirstName", ui."LastName"
            FROM {self.db_helper.time_sheet_table} ts
            JOIN {self.db_helper.user_table} ui ON ts."UserUUID" = ui."UserUUID"
            WHERE ui."User_manager" = :manager_uuid
            ORDER BY ts."Date" DESC
            LIMIT 5
            """
            params = {"manager_uuid": self.token_info["Id"]}
            rows = self.db_helper.execute_query(query, params)
            
            return [
                {
                    "ID": row["ID"],
                    "TIMN": row["TIMN"],
                    "TIMD": row["TIMD"],
                    "FullName": f"{row['FirstName']} {row['LastName']}",
                    "ClientName": row["ClientName"],
                    "ProjectName": row["ProjectName"],
                    "SOWName": row["SOWName"],
                    "ProjectBucket": row["ProjectBucket"],
                    "Date": row["Date"],
                    "HoursWorked": row["HoursWorked"],
                    "Status": row["Status"]
                }
                for row in rows
            ]
        except Exception as e:
            raise e

# Usage example
def get_manager_dashboard(db: Session, company_portal_url: str, token_info: Dict) -> Dict:
    try:
        print("here")
        manager_dashboard = ManagerDashboardExtension(db, company_portal_url, token_info)
        print("here")
        return manager_dashboard.get_manager_dashboard_data()
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise e
    
    

class HRDashboardExtension:
    def __init__(self, db: Session, company_portal_url: str, token_info: Dict, type: str):
        try:
            self.db = db
            self.token_info = token_info
            self.company_portal_url = company_portal_url
            if self.token_info["role"] != "HR":
                raise HTTPException(status_code=403, detail="Access denied, this is restricted to HR role")
            self.user = self._get_tenant_info()
            self.schema_name = self.user.SchemaName
            self.request_table = f"tb_{self.user.ShortName}_requests"
            self.request_sheet_table = f"{self.schema_name}.{self.request_table}"
            self.bgvtb = f"{self.schema_name}.tb_{self.user.ShortName}_bgv_info"
            self.type = type
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise e

    def _get_tenant_info(self):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user

    def get_hr_dashboard_data(self) -> Dict:
        print("\n type:", self.type)
        try:
            return {
                "pending_request_counts": self.get_pending_request_counts(),
                "last_five_pending_requests": self.get_last_five_pending_requests(),
                "application_count": self.get_bgv_users()
            }
        except Exception as e:
            raise e
    
    def get_bgv_users(self):
        query = f"""
            SELECT 
                COUNT(*) AS total_bgv,
                COUNT(CASE WHEN "status" = 'Pending' THEN 1 END) AS pending_count,
                COUNT(CASE WHEN "status" = 'Approved' THEN 1 END) AS approved_count,
                COUNT(CASE WHEN "status" = 'Denied' THEN 1 END) AS denied_count
            FROM {self.bgvtb}
        """
        result = self.db.execute(text(query)).fetchone()
        return {
            "total_bgv": result.total_bgv,
            "pending_count": result.pending_count,
            "approved_count": result.approved_count,
            "denied_count": result.denied_count,
        }

    def get_pending_request_counts(self) -> Dict[str, int]:
        try:
            query = text(f"""
            SELECT 
                SUM(CASE WHEN "RequestType" = 'HR' THEN 1 ELSE 0 END) as hr_count,
                SUM(CASE WHEN "RequestType" = 'ProfileEdit' THEN 1 ELSE 0 END) as profile_edit_count,
                SUM(CASE WHEN "RequestType" = 'Access' THEN 1 ELSE 0 END) as access_count
            FROM {self.request_sheet_table}
            WHERE "RequestStatus" = 'Pending'
            """)
            result = self.db.execute(query).fetchone()
            
            if result:
                return {
                    "HR_Requests": result.hr_count or 0,
                    "ProfileEdit_Requests": result.profile_edit_count or 0,
                    "Access_Requests": result.access_count or 0,
                    "Total_Pending": (result.hr_count or 0) + (result.profile_edit_count or 0) + (result.access_count or 0)
                }
            return {
                "HR_Requests": 0,
                "ProfileEdit_Requests": 0,
                "Access_Requests": 0,
                "Total_Pending": 0
            }
        except Exception as e:
            raise e

    def get_last_five_pending_requests(self) -> List[Dict]:
        try:
            where_clause = "WHERE r.\"RequestStatus\" = 'Pending'"
            if self.type:
                where_clause += f" AND r.\"RequestType\" = '{self.type}'"
            else:
                where_clause += " AND r.\"RequestType\" IN ('HR', 'ProfileChange', 'Access')"
                
            query = text(f"""
            SELECT 
                r."ID",
                r."RequestUUID",
                r."RequestType",
                r."RequestDetails",
                r."RequestAttachmentURL",
                r."RequestDescription",
                r."RequestStatus",
                r."RequestPriority",
                r."CreationTimeAndDate",
                r."UserUUID",
                ui."FirstName",
                ui."LastName",
                ui."Email"
            FROM {self.request_sheet_table} r
            JOIN {self.schema_name}.tb_{self.user.ShortName}_user_info ui 
                ON r."UserUUID" = ui."UserUUID"
            {where_clause}
            ORDER BY r."CreationTimeAndDate" DESC
            LIMIT 5
            """)
            
            rows = self.db.execute(query).fetchall()
            
            return [
                {
                    "ID": row.ID,
                    "RequestUUID": row.RequestUUID,
                    "RequestType": row.RequestType,
                    "RequestDetails": row.RequestDetails,
                    "Attachment": row.RequestAttachmentURL,
                    "Description": row.RequestDescription,
                    "Status": row.RequestStatus,
                    "CreatedAt": row.CreationTimeAndDate,
                    "RequesterName": f"{row.FirstName} {row.LastName}",
                    "RequesterEmail": row.Email
                }
                for row in rows
            ]
        except Exception as e:
            raise e

# Usage function
def get_hr_dashboard(db: Session, company_portal_url: str, token_info: Dict, type: str) -> Dict:
    try:
        print("here", type)
        hr_dashboard = HRDashboardExtension(db, company_portal_url, token_info, type)
        return hr_dashboard.get_hr_dashboard_data()
    except Exception as e:
        raise e
    
    
class AdminDashboard:
    def __init__(self, db: Session, company_portal_url: str, token_info: Dict):
        try:
            self.db = db
            self.token_info = token_info
            self.company_portal_url = company_portal_url
            if self.token_info["role"] != "Admin":
                return error.error("Access denied, this is restricted to HR role", 400, "Access Denied")
            self.user = self._get_tenant_info()
            self.schema_name = self.user.SchemaName
            self.setuptables()
        except Exception as e:
            return error.error(str(e), 500, "Admin Dashboard Error")
    
    def setuptables(self):
        self.usertb = f"{self.schema_name}.tb_{self.user.ShortName}_user_info"
        self.bgvtb = f"{self.schema_name}.tb_{self.user.ShortName}_bgv_info"
            
    def _get_tenant_info(self):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user
    
    def get_bgv_users(self):
        query = f"""
            SELECT 
                COUNT(*) AS total_bgv,
                COUNT(CASE WHEN "status" = 'Pending' THEN 1 END) AS pending_count,
                COUNT(CASE WHEN "status" = 'Approved' THEN 1 END) AS approved_count,
                COUNT(CASE WHEN "status" = 'Denied' THEN 1 END) AS denied_count
            FROM {self.bgvtb}
        """
        result = self.db.execute(text(query)).fetchone()
        return {
            "total_bgv": result.total_bgv,
            "pending_count": result.pending_count,
            "approved_count": result.approved_count,
            "denied_count": result.denied_count,
        }
    
    def get_user_role_counts(self):
        query = f"""
            SELECT 
                COUNT(*) AS total_users,
                COUNT(CASE WHEN "Role" = 'user' THEN 1 END) AS user_count,
                COUNT(CASE WHEN "Role" = 'Manager' THEN 1 END) AS manager_count,
                COUNT(CASE WHEN "Role" = 'HR' THEN 1 END) AS hr_count
            FROM {self.usertb}
        """
        result = self.db.execute(text(query)).fetchone()
        return {
            "total_users": result.total_users,
            "user_count": result.user_count,
            "manager_count": result.manager_count,
            "hr_count": result.hr_count,
        }
    
    def applications(self):
        query = f"""
            SELECT 
                u."UserUUID",
                u."FirstName", 
                u."LastName", 
                u."Email", 
                u."CreationTimeAndDate", 
                b."status" 
            FROM {self.usertb} AS u
            LEFT JOIN {self.bgvtb} AS b ON u."UserUUID" = b."UserUUID"
            WHERE u."User_bgv" = true 
            ORDER BY u."ID" DESC
            LIMIT 5
        """
        
        result = self.db.execute(text(query)).fetchall()
        
        return [
            {
                "UserUUID": str(row.UserUUID),
                "FirstName": row.FirstName,
                "LastName": row.LastName,
                "Email": row.Email,
                "CreationTimeAndDate": row.CreationTimeAndDate,
                "Status": row.status
            }
            for row in result
        ]
        
    def admindashboard(self):
        recent = self.applications()
        users = self.get_user_role_counts()
        applications = self.get_bgv_users()
        previous_month = (datetime.now() - relativedelta(months=1)).strftime('%B')
        
        return{
            "recetApplications": recent,
            "usersCount": users,
            "applicationStat": applications,
            "last_payDay": f"5 {previous_month}"
        }

