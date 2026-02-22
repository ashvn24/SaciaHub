import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import re
from typing import Dict, List, Optional
from uuid import UUID
import pytz
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging
from sqlalchemy.exc import SQLAlchemyError
from Models.Classes.ProjectManager import ProjectManager
from Models.Classes.ClientManager import ClientManager
from Models.Classes.SOWManager import SOWManager
from Models.Classes.GetUser import GetUser
from Models.Classes.Notification import ManageNotification
from Models.db.schemas import DeleteTimeSheet, TimesheetSchema, UpdateTimeSheet
from Models.db import models
from Models.Classes.TenantSettings import TenantSettingsManager
from Models.utils.send_mail import send_mail
import sys
import traceback
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()  

logger = logging.getLogger(__name__)


class TimesheetManagerStatus:
    def __init__(self, db: Session):
        self.db = db
    
    

    def _get_timesheet_table(self, customer):
        return f"{customer.SchemaName}.tb_{customer.ShortName}_timesheet"
    
    

    def _verify_admin(self, role):
        if role not in ["Admin", "Manager", "ClientRep", "HR"]:
            raise error.error("You do not have the permission to perform this action", 401, "Unauthorized")
    
   

    def _execute_update(self, timesheet_table, query_params):
        update_query = text(
            f"""
            UPDATE {timesheet_table}
            SET "Status" = :new_status,
                "FieldsUpdated" = :fields_updated,
                "FieldsValuesUpdated" = :fields_values_updated,
                "ApprovedBy" = :approvedUUid,
                "DeniedBy" = :DeniedBy
            WHERE "ID" = :id
        """
        )
        self.db.execute(update_query, query_params)
        # self.db.commit()

    async def approve_timesheet(self, data, token_info, customer):
        try:
            self._verify_admin(token_info["role"])
            print("Token Info:", token_info)
            timesheet_table = self._get_timesheet_table(customer)
            company_portal_url = customer.PortalURL
            user_table = f"{customer.SchemaName}.tb_{customer.ShortName}_user_info"
            
            # Get admin details
            admin_query = text(
                f"SELECT \"Email\", \"FirstName\", \"LastName\" FROM {user_table} WHERE \"UserUUID\" = :user_uuid"
            )
            admin_details = self.db.execute(admin_query, {"user_uuid": token_info["Id"]}).fetchone()
            admin_name = f"{admin_details.FirstName} {admin_details.LastName}" if admin_details else "System Admin"
            print(admin_name, "-------------admin_name---------------")
            
            # Fetch timesheet details
            fetch_query = text(
                f"""
                SELECT t."UserUUID", t."ID", t."Date", t."Status"
                FROM {timesheet_table} t
                WHERE t."ID" = ANY(:ids)
                """
            )
            current_statuses = self.db.execute(
                fetch_query, {"ids": data.ID}
            ).fetchall()

            fields_updated = json.dumps({"fields": ["Status"]})

            for timesheet in current_statuses:
                fields_values_updated = json.dumps(
                    {
                        "previous": {"Status": timesheet.Status},
                        "new": {"Status": data.Choice},
                    }
                )
                query_params = {
                    "new_status": "Approved" if data.Choice == "Approve" else "Denied",
                    "fields_updated": fields_updated,
                    "fields_values_updated": fields_values_updated,
                    "approvedUUid": token_info["Id"] if data.Choice == "Approve" else None,
                    "DeniedBy": token_info["Id"] if data.Choice == "Deny" else None,
                    "id": timesheet.ID,
                }
                self._execute_update(timesheet_table, query_params)

            # Handle notifications
            tenant_settings_manager = TenantSettingsManager(self.db, company_portal_url)
            print(tenant_settings_manager)
            is_notification_enabled = await tenant_settings_manager.is_timesheet_notification_enabled()
            print(is_notification_enabled, "------------------------")
            
            if is_notification_enabled:
                user_query = text(
                    f"SELECT \"Email\", \"FirstName\", \"LastName\" FROM {user_table} WHERE \"UserUUID\" = :user_uuid"
                )
                timesheet_status = data.Choice
                
                # Get all dates from timesheets
                timesheet_dates = [ts.Date for ts in current_statuses]
                timesheet_dates.sort()
                
                if len(timesheet_dates) > 1:
                    timesheet_date_str = f"{timesheet_dates[0].strftime('%B %d, %Y')} - {timesheet_dates[-1].strftime('%B %d, %Y')}"
                else:
                    timesheet_date_str = timesheet_dates[0].strftime("%B %d, %Y")

                # Send notifications for each user
                for timesheet in current_statuses:
                    user_details = self.db.execute(user_query, {"user_uuid": timesheet.UserUUID}).fetchone()
                    if user_details:
                        send_mail(
                            user_details.Email,
                            user_details.FirstName,
                            user_details.LastName,
                            "Timesheet Notification",
                            company_portal_url,
                            "Timesheet",
                            timesheet_status,
                            admin_name,
                            timesheet_date_str
                        )

                # Create notification
                try:
                    date_range = f"from {min(timesheet_dates)} to {max(timesheet_dates)}"
                    notification = ManageNotification(self.db, customer)
                    notification.create_notification(
                        type="Timesheet",
                        action=data.Choice,
                        to_uuid=str(timesheet.UserUUID),
                        from_uuid=token_info["Id"],
                        date=date_range
                    )
                except Exception as e:
                    logger.error(f"An unexpected error occurred: {str(e)}")
                    print(f"Error in create_notification: at line number {sys.exc_info()[-1].tb_lineno}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Notification creation failed",
                    )
            self.db.commit()
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Timesheets Updated successfully"},
            )

        except Exception as e:
            logger.error(f"An unexpected error occurred at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            print(f"Error in approve_timesheet at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            traceback.print_exc()
            raise e


class TimeSheetDBHelper:
    def __init__(self, db: Session, tenant_info):
        self.db = db
        self.tenant_info = tenant_info
        self.time_sheet_table = f"{self.tenant_info.SchemaName}.tb_{self.tenant_info.ShortName}_timesheet"
        self.user_table = f"{self.tenant_info.SchemaName}.tb_{self.tenant_info.ShortName}_user_info"
        self.reqtb = f"{self.tenant_info.SchemaName}.tb_{self.tenant_info.ShortName}_requests"

    def execute_query(self, query: str, params: Dict):
        result = self.db.execute(text(query), params)
        return result.mappings().all()

    def build_base_query(self, additional_joins="", filter_condition=""):
        query = f"""
        SELECT
            ts."ID", ts."TIMN", ts."TIMD", ts."UserUUID", ts."ClientUUID", ts."ClientName", ts."ProjectName", ts."SOWName", ts."ProjectUUID", ts."SOWUUID", ts."User_Manager",
            ts."ProjectBucket", ts."Month", ts."Date", ts."StartDate", ts."EndDate", ts."WorkDescription",
            ts."HoursWorked", ts."Status", ts."TimesheetAttachmentURL", ts."ApprovedBy", ts."DeniedBy",
            ui."FirstName" AS "UserFirstName", ui."LastName" AS "LastName",
            approver."FirstName" AS "ApprovedByFirstName",
            denier."FirstName" AS "DeniedByFirstName"
        FROM {self.time_sheet_table} ts
        LEFT JOIN {self.user_table} ui ON ts."UserUUID" = ui."UserUUID"
        LEFT JOIN {self.user_table} approver ON ts."ApprovedBy" = approver."UserUUID"
        LEFT JOIN {self.user_table} denier ON ts."DeniedBy" = denier."UserUUID"
        {additional_joins}
        """
        if filter_condition:
            if filter_condition.strip().upper().startswith('WHERE'):
                query += f" {filter_condition}"
            else:
                query += f" WHERE {filter_condition}"
        return query

    def build_weekly_query(self, filter_condition: str):
        return f"""
        SELECT
            tw."ID", tw."IDs", tw."WeekStartDate", tw."WeekEndDate", tw."TotalHours", tw."TIMWID",
            SUM(CASE WHEN t."Status" = 'Approved' THEN t."HoursWorked" ELSE 0 END) as "ApprovedHours",
            SUM(CASE WHEN t."Status" = 'Pending' THEN t."HoursWorked" ELSE 0 END) as "PendingHours",
            SUM(CASE WHEN t."Status" = 'Denied' THEN t."HoursWorked" ELSE 0 END) as "DeniedHours",
            SUM(t."HoursWorked") as "TotalHours",
            ui."FirstName", ui."LastName"
        FROM "{self.tenant_info.SchemaName}".tb_{self.tenant_info.ShortName}_timesheet_week tw
        LEFT JOIN "{self.tenant_info.SchemaName}".tb_{self.tenant_info.ShortName}_timesheet t
            ON t."ID" = ANY(tw."IDs"::int[])
        LEFT JOIN "{self.tenant_info.SchemaName}".tb_{self.tenant_info.ShortName}_user_info ui
            ON tw."UserUUID" = ui."UserUUID"
        WHERE {filter_condition}
        GROUP BY tw."ID", tw."IDs", tw."WeekStartDate", tw."WeekEndDate", tw."TotalHours", tw."TIMWID", ui."FirstName", ui."LastName"
        ORDER BY tw."WeekStartDate" DESC, ui."FirstName", ui."LastName"
        """

    def build_monthly_query(self, filter_condition: str):
        return f"""
        SELECT
            tm."ID", tm."IDs", tm."MonthStartDate", tm."MonthEndDate", tm."TotalHours", tm."TIMMID",
            SUM(CASE WHEN t."Status" = 'Approved' THEN t."HoursWorked" ELSE 0 END) as "ApprovedHours",
            SUM(CASE WHEN t."Status" = 'Pending' THEN t."HoursWorked" ELSE 0 END) as "PendingHours",
            SUM(CASE WHEN t."Status" = 'Denied' THEN t."HoursWorked" ELSE 0 END) as "DeniedHours",
            SUM(t."HoursWorked") as "TotalHours",
            ui."FirstName", ui."LastName"
        FROM "{self.tenant_info.SchemaName}".tb_{self.tenant_info.ShortName}_timesheet_month tm
        LEFT JOIN "{self.tenant_info.SchemaName}".tb_{self.tenant_info.ShortName}_timesheet t
            ON t."ID" = ANY(tm."IDs"::int[])
        LEFT JOIN "{self.tenant_info.SchemaName}".tb_{self.tenant_info.ShortName}_user_info ui
            ON tm."UserUUID" = ui."UserUUID"
        WHERE {filter_condition}
        GROUP BY tm."ID", tm."IDs", tm."MonthStartDate", tm."MonthEndDate", tm."TotalHours", tm."TIMMID", ui."FirstName", ui."LastName"
        ORDER BY tm."MonthStartDate" DESC, ui."FirstName", ui."LastName"
        """


class ViewTimeSheetManager:
    def __init__(self, db: Session, company_portal_url: str, token_info: Dict):
        self.db = db
        self.company_portal_url = company_portal_url
        self.token_info = token_info
        self.tenant_info = self._get_tenant_info()
        self.user_table = f"{self.tenant_info.SchemaName}.tb_{self.tenant_info.ShortName}_user_info"
        self.db_helper = TimeSheetDBHelper(db, self.tenant_info)
        GetUser(self.db, company_portal_url).verify_user(token_info)

    def _get_tenant_info(self):
        print("here")
        print("Company Portal URL:", self.company_portal_url)
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if user is None:
            raise HTTPException(
                status_code=404, detail={"message": "Schema not found"}
            )
        return user

    def get_time_sheets(
        self,
        day: Optional[str] = None,
        week: Optional[str] = None,
        month: Optional[str] = None,
        user_ids: Optional[List[str]] = None,
        Date: Optional[str] = None,
        param: Optional[str] = None,
        pagenum: Optional[int] = None,
        own: Optional[int] = None,
        status: Optional[str] = None,
        sortBy: Optional[str] = None,
        order: Optional[int] = 1,
        filterBy: Optional[str] = None,
    ) -> Dict:
        query_params, filter_condition = self._build_query_params(
            day, week, month, user_ids, Date, param, own, status
        )
        print("Weak", week)
        timesheets = self._execute_query(filter_condition, query_params, param, sortBy, order, filterBy)
        # Different grouping based on conditions
        if Date and user_ids:
            result_data = timesheets
        elif day or param == "All":
            result_data = timesheets
        else:
            group_by = "week" if week else "month"
            result_data = self._group_timesheets(timesheets, group_by)
            
        if pagenum is not None:
            print("page", pagenum)
            if not isinstance(result_data, list):
                raise ValueError("result_data must be a list to apply pagination.")
            if pagenum is None or pagenum == 0:
                pagenum = 1
            pagesize = 10
            # Apply pagination consistently to all cases
            totalitems = len(result_data)
            page_count = (totalitems // pagesize) + (1 if totalitems % pagesize > 0 else 0)
            
            result = None
            if result_data:
                if pagenum > 0 and pagenum <= page_count:
                    start_idx = (pagenum - 1) * pagesize
                    end_idx = start_idx + pagesize
                    try:
                        result = result_data[start_idx:end_idx]
                    except IndexError:
                        result = result_data[start_idx:]
            data = {}
            item = {"items": totalitems, "page": page_count}
            data["data"] = result
            data["total"] = item
            return data
        return result_data


    def _build_query_params(self, day, week, month, user_ids, Date, param=None, own= None, status=None):
        query_params = {}
        filter_conditions = []

        if day or week or month:
            start_date, end_date = self._get_date_range(day, week, month)
            filter_conditions.append(
                'ts."Date" >= :start_date AND ts."Date" <= :end_date')
            query_params["start_date"] = start_date
            query_params["end_date"] = end_date

        if week and param == "All":
            filter_conditions = [
                '"WeekStartDate" >= :start_date AND "WeekEndDate" <= :end_date']
        elif month and param == "All":
            filter_conditions = [
                '"MonthStartDate" >= :start_date AND "MonthEndDate" <= :end_date']

        if user_ids and Date:
            filter_conditions.append('ts."UserUUID" IN :UserUUIDs')
            filter_conditions.append('ts."Date" >= :start_date AND ts."Date" <= :end_date')
            query_params["UserUUIDs"] = tuple(user_ids)
            query_params["end_date"] = datetime(2024, 12, 1, 0, 0, tzinfo=pytz.UTC)
            query_params["start_date"] = datetime(2024, 11, 1, 0, 0, tzinfo=pytz.UTC)

        self._add_role_specific_conditions(
            filter_conditions, query_params, user_ids, own
        )

        if status:
            filter_conditions.append('ts."Status" = :status')
            query_params["status"] = status

        return query_params, " AND ".join(filter_conditions)

    def _add_role_specific_conditions(self, filter_conditions, query_params, user_ids, own = None):
        if user_ids and self.token_info["role"] in ["Admin", "Manager", "ClientRep"]:
            filter_conditions.append('ts."UserUUID" IN :UserUUIDs')
            query_params["UserUUIDs"] = tuple(user_ids)

        if self.token_info["role"] in ["user", "HR"]:
            filter_conditions.append('ui."UserUUID" = :UserUUID')
            query_params["UserUUID"] = self.token_info["Id"]
        elif self.token_info["role"] == "Manager" and own == 0:
            filter_conditions.append('ui."User_manager" = :ManagerUUID')
            query_params["ManagerUUID"] = self.token_info["Id"]
        elif self.token_info["role"] in ["Manager", "Admin"] and own == 1:
            filter_conditions.append('ui."UserUUID" = :UserUUID')
            query_params["UserUUID"] = self.token_info["Id"]
        elif self.token_info["role"] == "ClientRep":
            filter_conditions.append('(ui."User_ClientRep" = :User_ClientRep OR ui."UserUUID" = :User_ClientRep)')
            query_params["User_ClientRep"] = self.token_info["Id"]

    def _execute_query(
        self,
        filter_condition: Optional[str],
        query_params: Optional[Dict],
        param: Optional[str],
        sortBy: Optional[str],
        order: Optional[int],
        filterBy: Optional[str],
    ):
        try:
            print("\n----------------Sort By----------------:", sortBy)
            print("\n----------------Order----------------:", order)
            # Handle "All" param path for pre-aggregated weekly/monthly views
            if param == "All":
                if self.token_info["role"] == "Admin":
                    if "WeekStartDate" in filter_condition:
                        return self._execute_weekly_query(filter_condition, query_params)
                    elif "MonthStartDate" in filter_condition:
                        return self._execute_monthly_query(filter_condition, query_params)

                elif self.token_info["role"] in ["Manager", "ClientRep"]:
                    if "WeekStartDate" in filter_condition:
                        return self._execute_weekly_query_manager_or_client_rep(filter_condition, query_params)
                    elif "MonthStartDate" in filter_condition:
                        return self._execute_monthly_query_manager_or_client_rep(filter_condition, query_params)

                elif self.token_info["role"] in ["user", "HR"]:
                    if "WeekStartDate" in filter_condition:
                        return self._execute_weekly_query_user(filter_condition, query_params)
                    elif "MonthStartDate" in filter_condition:
                        return self._execute_monthly_query_user(filter_condition, query_params)
            

            if isinstance(filterBy, str):
                try:
                    filterBy = json.loads(filterBy)
                except ValueError:
                    filterBy = {}
            
            filter_clauses = []

            if filterBy:
            
                if "FullName" in filterBy and filterBy["FullName"] is not None:
                    filter_clauses.append("""(LOWER(ui."FirstName") || ' ' || LOWER(ui."LastName")) LIKE :full_name""")
                    query_params["full_name"] = f"%{filterBy['FullName'].lower()}%"

                if "ClientName" in filterBy and filterBy["ClientName"] is not None:
                    filter_clauses.append("""LOWER(ts."ClientName") LIKE :client_name""")
                    query_params["client_name"] = f"%{filterBy['ClientName'].lower()}%"

                if "ProjectName" in filterBy and filterBy["ProjectName"] is not None:
                    filter_clauses.append("""LOWER(ts."ProjectName") LIKE :project_name""")
                    query_params["project_name"] = f"%{filterBy['ProjectName'].lower()}%"

                if "SOWName" in filterBy and filterBy["SOWName"] is not None:
                    filter_clauses.append("""LOWER(ts."SOWName") LIKE :sow_name""")
                    query_params["sow_name"] = f"%{filterBy['SOWName'].lower()}%"

                if "WorkDescription" in filterBy and filterBy["WorkDescription"] is not None:
                    filter_clauses.append("""LOWER(ts."WorkDescription") LIKE :task""")
                    query_params["task"] = f"%{filterBy['WorkDescription'].lower()}%"

                if "Month" in filterBy and filterBy["Month"] is not None:
                    filter_clauses.append("""ts."Month" = :month""")
                    query_params["month"] = str(filterBy["Month"])
                
                if "Period" in filterBy and filterBy["Period"] is not None:
                    start_date, end_date = [d.strip() for d in filterBy["Period"].split("to")]
                    filter_clauses.append("""ts."Date" BETWEEN :start_date AND :end_date""")
                    query_params["start_date"] = start_date
                    query_params["end_date"] = end_date
                
                if "Status" in filterBy and filterBy["Status"] is not None:
                    filter_clauses.append("""ts."Status" = :status""")
                    query_params["status"] = filterBy["Status"]

                # Append extra filters to filter_condition
                if filter_clauses:
                    if filter_condition:
                        if "WHERE" in filter_condition.upper():
                            # If filter_condition already has WHERE, just add AND and the new conditions
                            filter_condition += " AND " + " AND ".join(filter_clauses)
                        else:
                            # If filter_condition doesn't have WHERE, add it
                            filter_condition = "WHERE " + filter_condition + " AND " + " AND ".join(filter_clauses)
                    else:
                        # If no existing filter_condition, just add WHERE and the new conditions
                        filter_condition = "WHERE " + " AND ".join(filter_clauses)

            # Build base query
            query = self.db_helper.build_base_query(filter_condition=filter_condition)

            # Allowed sortable columns — whitelist to prevent SQL injection
            allowed_sort_columns = {
                "Date": 'ts."Date"',
                "HoursWorked": 'ts."HoursWorked"',
                "Status": 'ts."Status"',
                "ClientName": 'ts."ClientName"',
                "ProjectName": 'ts."ProjectName"',
                "User_Manager": 'ts."User_Manager"',
                "Month": 'ts."Month"',
                "TIMN": 'ts."TIMN"',
                "TIMD": 'ts."TIMD"',
                "ApprovedBy": 'ts."ApprovedBy"',
                "WorkDescription": 'ts."WorkDescription"',
                "ProjectBucket": 'ts."ProjectBucket"',
                "TimeSheetAttachmentURL": 'ts."TimeSheetAttachmentURL"',
                "FirstName": 'ui."FirstName"'
            }

            # Default sorting if nothing is passed
            if sortBy and sortBy in allowed_sort_columns:
                direction = "ASC" if order == 1 else "DESC"
                order_clause = f' ORDER BY {allowed_sort_columns[sortBy]} {direction}'
            else:
                # Default sort: Date DESC, FirstName ASC
                order_clause = ' ORDER BY ts."Date" DESC, ui."FirstName" ASC'

            # Append order clause
            query += order_clause

            # Execute query
            rows = self.db_helper.execute_query(query, query_params)

            # Format and return
            return self._format_timesheet_rows(rows)

        except SQLAlchemyError as e:
            print(f"Database error: {str(e)}")
            logger.error(f"Database error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred"
            )


    def _execute_weekly_query(self, filter_condition: str, query_params: Dict):
        try:
            query = self.db_helper.build_weekly_query(filter_condition)
            rows = self.db_helper.execute_query(query, query_params)
            return self._format_weekly_monthly_rows(rows)
        except SQLAlchemyError as e:
            print(f"Database error: {str(e)}")
            logger.error(f"Database error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred"
            )

    def _execute_monthly_query(self, filter_condition: str, query_params: Dict):
        query = self.db_helper.build_monthly_query(filter_condition)
        rows = self.db_helper.execute_query(query, query_params)
        return self._format_weekly_monthly_rows(rows)

    def _execute_weekly_query_manager_or_client_rep(self, filter_condition: str, query_params: Dict):
        if self.token_info["role"] == "Manager":
            additional_condition = '(ui."User_manager" = :UserUUID OR ui."UserUUID" = :UserUUID)'
        else:  # ClientRep
            additional_condition = '(ui."User_ClientRep" = :UserUUID OR ui."UserUUID" = :UserUUID)'
        
        query = self.db_helper.build_weekly_query(
            filter_condition + f' AND {additional_condition}')
        query_params["UserUUID"] = self.token_info["Id"]
        rows = self.db_helper.execute_query(query, query_params)
        return self._format_weekly_monthly_rows(rows)

    def _execute_monthly_query_manager_or_client_rep(self, filter_condition: str, query_params: Dict):
        if self.token_info["role"] == "Manager":
            additional_condition = '(ui."User_manager" = :UserUUID OR ui."UserUUID" = :UserUUID)'
        else:  # ClientRep
            additional_condition = '(ui."User_ClientRep" = :UserUUID OR ui."UserUUID" = :UserUUID)'
        
        query = self.db_helper.build_monthly_query(
            filter_condition + f' AND {additional_condition}')
        query_params["UserUUID"] = self.token_info["Id"]
        rows = self.db_helper.execute_query(query, query_params)
        return self._format_weekly_monthly_rows(rows)

    def _execute_weekly_query_user(self, filter_condition: str, query_params: Dict):
        query = self.db_helper.build_weekly_query(
            filter_condition + ' AND ui."UserUUID" = :UserUUID')
        query_params["UserUUID"] = self.token_info["Id"]
        rows = self.db_helper.execute_query(query, query_params)
        return self._format_weekly_monthly_rows(rows)

    def _execute_monthly_query_user(self, filter_condition: str, query_params: Dict):
        query = self.db_helper.build_monthly_query(
            filter_condition + ' AND ui."UserUUID" = :UserUUID')
        query_params["UserUUID"] = self.token_info["Id"]
        rows = self.db_helper.execute_query(query, query_params)
        return self._format_weekly_monthly_rows(rows)

    def _format_timesheet_rows(self, rows):
        sowdata = SOWManager(self.db, self.token_info, self.company_portal_url)
        cdata = ClientManager(self.db, self.token_info, self.company_portal_url)
        pdata = ProjectManager(self.db, self.token_info, self.company_portal_url)
        
        return [
            {
                "ID": row["ID"],
                "UserUUID": row["UserUUID"],
                "TIMN": row["TIMN"],
                "TIMD": row["TIMD"],
                "FullName": (row["UserFirstName"] or "") + " " + (row["LastName"] or ""),
                "ClientName": cdata._get_client(clientuuid= row["ClientUUID"])[0]["ClientName"] if row["ClientUUID"] else row["ClientName"],
                "ProjectName": pdata._get_project(projectuuid= row["ProjectUUID"])[0]["ProjectName"] if row["ProjectUUID"] else row["ProjectName"],
                "SOWName":sowdata._get_sow(sowuuid = row["SOWUUID"])[0]["SOWName"] if row["SOWUUID"] else row["SOWName"],
                "User_Manager": row["User_Manager"],
                "ProjectBucket": row["ProjectBucket"],
                "Month": row["Month"],
                "Date": row["Date"],
                "StartDate": row["StartDate"],
                "EndDate": row["EndDate"],
                "Notes": row["WorkDescription"],
                "HoursWorked": f"{float(row["HoursWorked"]) :.1f}",
                "Status": row["Status"],
                "TimesheetAttachmentURL": row["TimesheetAttachmentURL"],
                "ApprovedBy": row["ApprovedByFirstName"] if row["ApprovedByFirstName"] else row["DeniedByFirstName"],
            }
            for row in rows
        ]

    def _format_weekly_monthly_rows(self, rows):
        return [
            {
                "ID": row["ID"],
                "WeekStartDate": row.get("WeekStartDate"),
                "WeekEndDate": row.get("WeekEndDate"),
                "MonthStartDate": row.get("MonthStartDate"),
                "MonthEndDate": row.get("MonthEndDate"),
                "TotalHours": row["TotalHours"],
                "TIMWID": row.get("TIMWID"),
                "TIMMID": row.get("TIMMID"),
                "TimeSheetIDs": set(row["IDs"]),
                "ApprovedHours": f"{float(row["ApprovedHours"]): .1f}",
                "PendingHours": f"{float(row["PendingHours"]): .1f}",
                "DeniedHours": f"{float(row["DeniedHours"]): .1f}",
                "FullName": f"{row['FirstName']} {row['LastName']}"
            }
            for row in rows
        ]

    def _group_timesheets(self, timesheets: List[Dict], group_by: str) -> Dict:
        try:
            if self.token_info["role"] in ["Admin", "Manager"]:
                return self._group_timesheets_admin(timesheets, group_by)
            else:
                return self._group_timesheets_user(timesheets, group_by)
        except Exception as e:
            print(f"Error in grouping timesheets: {str(e)}")
            logger.error(f"Error in grouping timesheets: {str(e)}")
            raise e

    def _group_timesheets_admin(self, timesheets: List[Dict], group_by: str) -> Dict:
        grouped_timesheets = defaultdict(lambda: defaultdict(
            lambda: defaultdict(self._create_default_entry)))
        


        for ts in timesheets:
            approved_by = ts.get("ApprovedBy")
            denied_by = ts.get("DeniedBy")
            if approved_by:
                ts["processed_by_name"] = approved_by
            elif denied_by:
                ts["processed_by_name"] = denied_by
            else:
                ts["processed_by_name"] = None
            time_key = self._get_time_key(ts["Date"], group_by)
            user_name = ts["FullName"]
            project_key = (ts["ClientName"],
                           ts["ProjectName"], ts["ProjectBucket"])
            entry = grouped_timesheets[time_key][user_name][project_key]
            self._update_entry(entry, ts)

        return self._format_grouped_timesheets(grouped_timesheets)

    def _group_timesheets_user(self, timesheets: List[Dict], group_by: str) -> Dict:
        grouped_timesheets = defaultdict(
            lambda: defaultdict(self._create_default_entry))
        


        for ts in timesheets:
            approved_by = ts.get("ApprovedBy")
            denied_by = ts.get("DeniedBy")
            if approved_by:
                ts["processed_by_name"] = approved_by
            elif denied_by:
                ts["processed_by_name"] = denied_by
            time_key = self._get_time_key(ts["Date"], group_by)
            project_key = (ts["ClientName"],
                           ts["ProjectName"], ts["ProjectBucket"])
            entry = grouped_timesheets[time_key][project_key]
            self._update_entry(entry, ts)

        return {
            time_key: list(projects.values())
            for time_key, projects in grouped_timesheets.items()
        }

    @staticmethod
    def _create_default_entry():
        return {
            "ID": set(),
            "client_name": "",
            "project_name": "",
            "sow_name": "",
            "task": "",
            "total_hours": 0.0,  # Initialize as float
            "approved_hours": 0.0,  # Initialize as float 
            "denied_hours": 0.0,  # Initialize as float
            "pending_hours": 0.0,  # Initialize as float
            "attachment": set(),
            "status": set(),
        }

    def _update_entry(self, entry: Dict, ts: Dict) -> None:
        try:
            # Convert hours to float before adding
            hours_worked = float(ts["HoursWorked"]) if isinstance(ts["HoursWorked"], str) else ts["HoursWorked"]
            
            entry["client_name"] = ts["ClientName"]
            entry["project_name"] = ts["ProjectName"]
            entry["task"] = ts["ProjectBucket"]
            entry["sow_name"] = ts["SOWName"]
            entry["total_hours"] += hours_worked

            if ts["Status"] == "Approved":
                entry["approved_hours"] += hours_worked
            elif ts["Status"] == "Denied":
                entry["denied_hours"] += hours_worked
            elif ts["Status"] == "Pending":
                entry["pending_hours"] += hours_worked

            entry["attachment"].add(ts["TimesheetAttachmentURL"])
            entry["ID"].add(ts["ID"])
            entry["status"].add(ts["Status"])

        except Exception as e:
            logger.error(f"Error updating timesheet entry: {str(e)}")
            logger.error(f"Timesheet data: {ts}")
            logger.error(f"Entry data: {entry}")
            raise ValueError(f"Error processing timesheet hours: {str(e)}")

    def _format_grouped_timesheets(self, grouped_timesheets: Dict) -> Dict:
        result = {}
        for time_key, users in grouped_timesheets.items():
            result[time_key] = {}
            for user_name, projects in users.items():

                result[time_key][user_name] = [
                    {
                        "ID": sorted(list(entry["ID"])),
                        "client_name": entry["client_name"],
                        "project_name": entry["project_name"],
                        "sow_name": entry["sow_name"],
                        "task": entry["task"],
                        "total_hours": f"{float(entry["total_hours"]) :.1f}",
                        "ApprovedHours": f"{float(entry["approved_hours"]) :.1f}",
                        "DeniedHours": f"{float(entry["denied_hours"]) :.1f}",
                        "PendingHours": f"{float(entry["pending_hours"]) :.1f}",
                        "attachment": list(entry["attachment"]),
                        "status": list(entry["status"])[0] if len(entry["status"]) == 1 else list(entry["status"]),
                        "processed_by_name": entry.get("processed_by_name")  # Add this line
                    }
                    for entry in projects.values()
                ]
        return result

    @staticmethod
    def _get_time_key(date, group_by):
        date = ViewTimeSheetManager._ensure_date(date)
        if group_by == "week":
            week_start = date - timedelta(days=date.weekday())
            week_end = week_start + timedelta(days=6)
            return f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
        else:  # month
            return date.strftime("%Y-%m")

    @staticmethod
    def _ensure_date(date_value):
        if isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        elif isinstance(date_value, datetime):
            return date_value.date()
        return date_value

    @staticmethod
    def _get_month_range(year: int, month: int):
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day, 23, 59, 59, 999999)
        return start_date, end_date

    @staticmethod
    def _get_week_ranges(year: int, month: int):
        first_day = datetime(year, month, 1)
        _, last_day_of_month = calendar.monthrange(year, month)
        last_day = datetime(year, month, last_day_of_month, 23, 59, 59, 999999)

        week_ranges = []
        current_week_start = first_day - timedelta(days=first_day.weekday())

        while current_week_start <= last_day:
            week_end = current_week_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            week_ranges.append(
                (max(current_week_start, first_day), min(week_end, last_day))
            )
            current_week_start += timedelta(days=7)

        return week_ranges

    def _get_date_range(self, day, week, month):
        if day:
            year, month = map(int, day.split("-"))
            return self._get_month_range(year, month)
        elif week:
            year, month = map(int, week.split("-"))
            week_ranges = self._get_week_ranges(year, month)
            return min(start for start, _ in week_ranges), max(end for _, end in week_ranges)
        elif month:
            year, month = map(int, month.split("-"))
            return self._get_month_range(year, month)
        else:
            raise ValueError("Invalid date parameter")


class CreateTimeSheetManager:
    def __init__(self, db: Session, token_info: Dict, Company_Portal_Url: str):
        self.db = db
        self.token_info = token_info
        self.customer = self._getCustomer(Company_Portal_Url)
        self.notification = ManageNotification(self.db, self.customer)
        self.admin = self._get_admin(Company_Portal_Url)
        self.company_portal_url = Company_Portal_Url
        self.uuid = None
        self.status = "Pending"
        GetUser(self.db, Company_Portal_Url).verify_user(token_info)

    def _getCustomer(self, company_portal_url: str):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        return user
    
    def _get_all_admins(self, Company_Portal_Url):
        if Company_Portal_Url is not None:
            user = self._getCustomer(Company_Portal_Url)
            user_table_name = f"{user.SchemaName}.tb_{
                user.ShortName}_user_info"
            select_query = text(f"""
                SELECT "UserUUID", "Role"
                FROM {user_table_name}
                WHERE "Role" IN ('Admin', 'Manager')
            """)

            result = self.db.execute(select_query).mappings().all()
            print("All Admins:", result)
            return result
        return None
    
    def _get_admin(self, Company_Portal_Url):
        company_schema_name, company_shortname = self._get_company_info(
            Company_Portal_Url
        )
        user_table_name = f"{company_schema_name}.tb_{
            company_shortname}_user_info"
        select_query = text(
            f'SELECT "UserUUID" FROM {user_table_name} WHERE "Role" = :role'
        )
        result = self.db.execute(select_query, {"role": "Admin"})
        print("Result:", result)
        return result.mappings().fetchone()
    
    def get_assigned_hr(self, Company_Portal_Url: str, user_uuid: str):
        company_schema_name, company_shortname = self._get_company_info(Company_Portal_Url)
        user_table_name = f"{company_schema_name}.tb_{company_shortname}_user_info"

        query = text(f'''
            SELECT "HR_Manager"
            FROM {user_table_name}
            WHERE "UserUUID" = :user_uuid
        ''')
        result = self.db.execute(query, {"user_uuid": user_uuid}).mappings().fetchone()
        print("Result:",result)
        return result["HR_Manager"] if result else None


    def _get_company_info(self, company_portal_url: str):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Schema not found")
        return user.SchemaName, user.ShortName

    def _get_tenant(self, Company_portal_Url):
        SchemaName, ShortName = self._get_company_info(Company_portal_Url)
        tenant_table = f"{SchemaName}.tb_{ShortName}_tenant_info"
        select_query = text(
            f"""
            SELECT "TenantUUID" from {tenant_table}
            """
        )
        result = self.db.execute(select_query)
        tenant = result.mappings().one()
        return tenant.get("TenantUUID")

    def _verify_user(self, company_schema_name: str, company_shortname: str):
        user_table_name = f"{company_schema_name}.tb_{
            company_shortname}_user_info"
        dynamic_query_email = text(
            f'SELECT * FROM {user_table_name} WHERE "UserUUID" = :UserUUID'
        )
        existing_user_email = self.db.execute(
            dynamic_query_email, {"UserUUID": self.token_info["Id"]}
        ).fetchone()
        if not existing_user_email:
            raise HTTPException(status_code=404, detail="User not found")

    def _distribute_hours(
        self, start_date: datetime, end_date: datetime, hours_worked: float
    ):
        num_days = (end_date - start_date).days + 1
        return hours_worked / num_days

    async def create_time_sheet(self, data: TimesheetSchema, request:Request):
        self.request = request.client.host
        token_info = self.token_info
        user_uuid = token_info["Id"]
        print("tim1")
        try:
            if not isinstance(data, TimesheetSchema):
                self.status = "Approved"
                self.uuid = data["uuid"]
                self.missedData = True
                data = TimesheetSchema(**data)
            company_schema_name, company_shortname = self._get_company_info(
                data.Company_Portal_Url
            )
            self._verify_user(company_schema_name, company_shortname)
            user_table = f"{company_schema_name}.tb_{
                company_shortname}_user_info"
            
            print("User Table:--", user_table)

            time_sheet_table = f"{company_schema_name}.tb_{
                company_shortname}_timesheet"
            for timesheet_entry in data.Timesheet:
                for entry in timesheet_entry.time:
                    time_entries = timesheet_entry.time
                    start_dates = [entry.StartDate for entry in time_entries]
                    end_dates = [entry.EndDate for entry in time_entries]
                    overall_start = min(start_dates)
                    overall_end = max(end_dates)
                    formatted_start = overall_start.strftime('%B %d, %Y')
                    formatted_end = overall_end.strftime('%B %d, %Y')
                    formatted_range = f"{formatted_start} to {formatted_end}"

                    if entry.StartDate > entry.EndDate:
                        raise HTTPException(
                            status_code=400, detail="StartDate cannot be after EndDate"
                        )

                    distributed_hours_per_day = self._distribute_hours(
                        entry.StartDate, entry.EndDate, entry.HoursWorked
                    )

                    current_date = entry.StartDate
                    while current_date <= entry.EndDate:
                        self._insert_timesheet_entry(
                            time_sheet_table,
                            data,
                            timesheet_entry,
                            entry,
                            current_date,
                            distributed_hours_per_day,
                            user_uuid
                        )
                        current_date += timedelta(days=1)

            # Send email notifications to admins if enabled
            tenant_settings_manager = TenantSettingsManager(self.db, data.Company_Portal_Url)
            is_notification_enabled = await tenant_settings_manager.is_timesheet_notification_enabled()
            if is_notification_enabled:
                admin_details = self.db.execute(text(f"SELECT \"Email\", \"FirstName\", \"LastName\" FROM {user_table} WHERE \"Role\" = 'Admin'")).fetchall()
                user_details = self.db.execute(text(f"SELECT \"FirstName\", \"LastName\" FROM {user_table} WHERE \"UserUUID\" = :UserUUID"), {"UserUUID": self.token_info["Id"]}).fetchone()
                user_name = f"{user_details[0]} {user_details[1]}" if user_details[0] and user_details[1] else "User"
                for admin in admin_details:
                    admin_name = f"{admin[1]} {admin[2]}" if admin[1] and admin[2] else "System Admin"
                    try:
                        send_mail(
                            admin[0],  
                            user_name,  
                            admin[2],  
                            "Timesheet Notification Admin",  # Changed to match send_mail.py condition
                            data.Company_Portal_Url,
                            "Timesheet",
                            "Created",
                            admin_name,
                            formatted_range,
                            "Timesheet"
                        )
                    except Exception as e:
                        print(f"Error sending email at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                        raise HTTPException(status_code=500, detail="An error occurred while sending the email.")
                

            return JSONResponse(
                status_code=201, content={"message": "TimeSheet created successfully"}
            )
        except HTTPException as http_exc:
            raise http_exc
        except (SQLAlchemyError, Exception) as e:
            print(f"Exception at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            self._handle_exception(e)

    def update_time_sheet(self, data: UpdateTimeSheet):
        try:
            company_schema_name, company_shortname = self._get_company_info(
                data.Company_Portal_Url
            )
            time_sheet_table = f"{company_schema_name}.tb_{
                company_shortname}_timesheet"

            existing_timesheet = self._check_timesheet_exists(
                time_sheet_table, data.TimeSheetID
            )
            if not existing_timesheet:
                raise error.error("Timesheet not found or does not belong to the user", 404, "Not Found")

            self._update_existing_timesheet(time_sheet_table, data)

            if len(data.time) > 1:
                self._create_additional_timesheets(time_sheet_table, data)

            self.db.commit()
            return JSONResponse(
                status_code=200, content={"message": "TimeSheet updated successfully"}
            )
        except (HTTPException, SQLAlchemyError) as e:
            self._handle_exception(e)

    def delete_time_sheets(self, data: DeleteTimeSheet):
        try:
            company_schema_name, company_shortname = self._get_company_info(
                data.Company_Portal_Url
            )
            self._verify_user(company_schema_name, company_shortname)

            time_sheet_table = f"{company_schema_name}.tb_{company_shortname}_timesheet"

            if not data.TimeSheet_Ids:
                raise error.error("No timesheet IDs provided for deletion", 400, "Bad Request")

            self._delete_timesheets(time_sheet_table, data.TimeSheet_Ids)

            self.db.commit()
            return JSONResponse(
                status_code=200,
                content={"message": "Selected timesheets deleted successfully"},
            )
        except (HTTPException, SQLAlchemyError) as e:
            print(e)
            self._handle_exception(e)

    def _insert_timesheet_entry(
        self,
        time_sheet_table: str,
        data: TimesheetSchema,
        timesheet_entry,
        entry,
        current_date: datetime,
        hours_worked: float,
        user_uuid: str = None
    ):
        Hours = hours_worked
        ID, TIMN, TIMD, TIMM, TIMW = self._get_TMdata()
        if data.Timesheet[0].Client_Name == self.customer.ShortName:
            query = f"""
            SELECT "TIMD", "HoursWorked", "Status", "ProjectBucket" FROM {time_sheet_table}
            WHERE "UserUUID" = :UserUUID AND "Date" = :Date
            AND "ClientName" = :ClientName AND "ProjectName" = :ProjectName AND "ProjectBucket" = :ProjectBucket
            """
        else:
            query = f"""
                SELECT "TIMD", "HoursWorked", "Status", "ProjectBucket" FROM {time_sheet_table}
                WHERE "UserUUID" = :UserUUID AND "Date" = :Date
                AND (
                    ("ClientName" = :ClientName OR "ClientUUID" = :ClientName)
                )
                AND (
                    ("ProjectName" = :ProjectName OR "ProjectUUID" = :ProjectName)
                )
                AND "ProjectBucket" = :ProjectBucket
                """
        existing_entry_query = text(query)
            
        existing_entry = (
            self.db.execute(
                existing_entry_query,
                {
                    "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                    "Date": current_date,
                    "ClientName": timesheet_entry.Client_Name,
                    "ProjectName": timesheet_entry.Project_Name,
                    "ProjectBucket": timesheet_entry.Project_Task,
                },
            )
            .mappings()
            .first()
        )
        if existing_entry and existing_entry["Status"] == "Pending" and existing_entry["ProjectBucket"] == timesheet_entry.Project_Task:
            TIMD = existing_entry["TIMD"]
            hours_worked += int(existing_entry["HoursWorked"])
            if data.Timesheet[0].Client_Name == self.customer.ShortName:
                query = f"""
                UPDATE {time_sheet_table}
                SET "HoursWorked" = :hours_worked
                WHERE "UserUUID" = :UserUUID AND "Date" = :Date
                AND "ClientName" = :ClientName AND "ProjectName" = :ProjectName AND "ProjectBucket" = :ProjectBucket
                """
            else:
                query = f"""
                UPDATE {time_sheet_table}
                SET "HoursWorked" = :hours_worked
                WHERE "UserUUID" = :UserUUID AND "Date" = :Date
                AND (
                    ("ClientName" = :ClientName OR "ClientUUID" = :ClientName)
                )
                AND (
                    ("ProjectName" = :ProjectName OR "ProjectUUID" = :ProjectName)
                )
                AND "ProjectBucket" = :ProjectBucket
                """
            update_query = text(query)
            self.db.execute(
                update_query,
                {
                    "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                    "Date": current_date,
                    "ClientName": timesheet_entry.Client_Name,
                    "ProjectName": timesheet_entry.Project_Name,
                    "ProjectBucket": timesheet_entry.Project_Task,
                    "hours_worked": hours_worked,
                },
            )
            self.db.commit()
            update_query_week = text(
                f"""
                UPDATE {self.customer.SchemaName}.tb_{self.customer.ShortName}_timesheet_week
                SET "TotalHours" = "TotalHours" + :hours_worked, "IDs" = array_append("IDs", :NewID)
                WHERE "UserUUID" = :UserUUID AND :Date BETWEEN "WeekStartDate" AND "WeekEndDate"
                """
            )
            print(current_date - timedelta(days=current_date.weekday()))
            # week_start, week_end = self._get_week_start_end(current_date)
            self.db.execute(
                update_query_week,
                {
                    "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                    "hours_worked": Hours,
                    "Date": current_date,
                    "NewID": ID,
                },
            )
            self.db.commit()

            self._update_or_insert_month_record(current_date, Hours, ID)

        else:
            print("tim2")
            TIMD = f"TIMD{int(TIMD[4:]) + 1:06d}"
            print("TIMD", TIMD)
            insert_query = text(
                f"""
                INSERT INTO {time_sheet_table} (
                    "UserUUID", "ClientName", "ProjectName", "SOWName", "User_Manager", "ProjectBucket",
                    "Month", "Date", "StartDate", "EndDate", "WorkDescription", "HoursWorked", "Status", "TimesheetAttachmentURL",
                    "IPAddress", "Latitude", "Longitude", "UpdatedTimeAndDate", "TenantUUID", "RequestedBy", "SOWUUID",
                    "ProjectUUID", "ClientUUID", "VendorName", "TIMD", "TIMN"
                ) VALUES (
                    :UserUUID, :ClientName, :ProjectName, :SOWName, :User_Manager, :ProjectBucket,
                    :Month, :Date, :StartDate, :EndDate, :WorkDescription, :HoursWorked, :Status, :TimesheetAttachmentURL,
                    :IPAddress, :Latitude, :Longitude, :UpdatedTimeAndDate, :TenantUUID, :RequestedBy, :SOWUUID,
                    :ProjectUUID, :ClientUUID, :VendorName, :TIMD, :TIMN
                )RETURNING "ID"
                """
            )
            SchemaName, ShortName = self._get_company_info(
                data.Company_Portal_Url)
            timesheetWeek = f"{SchemaName}.tb_{ShortName}_timesheet_week"
            print("\n enrtyy:::", timesheet_entry)
            if timesheet_entry.Project_Name != "Internal" or timesheet_entry.Project_Task == "Time Off" or timesheet_entry.Client_Name != ShortName:
                print("here..........")
                check_week_query, update_week_query, insert_query_week = self.insertweekTIM(timesheetWeek)
            print("tim3")
            tenantUUID = self._get_tenant(data.Company_Portal_Url)
            project_sow_table = f"{SchemaName}.tb_{ShortName}_sow_info"
            project_table = f"{SchemaName}.tb_{ShortName}_project_info"
            result_data = None
            if timesheet_entry.SOW_Name and timesheet_entry.Project_Name not in [None, "Internal"]:
                select_query = text(
                    f"""
                    SELECT s."SOWName", s."ProjectName", p."ClientName", p."VendorUUID"
                    FROM {project_sow_table} s
                    JOIN {project_table} p ON s."ProjectUUID" = p."ProjectUUID"
                    WHERE s."SOWUUID" = :sow_name AND p."ProjectUUID" = :project_name
                    LIMIT 1
                    """
                )
                result = self.db.execute(
                    select_query,
                    {
                        "sow_name": timesheet_entry.SOW_Name,
                        "project_name": timesheet_entry.Project_Name,
                    },
                )
                result_data = result.mappings().one_or_none()
            print("res",result_data)
            timsheetresult = self.db.execute(
                insert_query,
                {
                    "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                    "ClientName": result_data.get("ClientName") if result_data is not None else timesheet_entry.Client_Name,
                    "ProjectName": result_data.get("ProjectName") if result_data is not None else timesheet_entry.Project_Name,
                    "SOWName": result_data.get("SOWName") if result_data is not None else timesheet_entry.SOW_Name,
                    "User_Manager": data.User_Manager,
                    "ProjectBucket": timesheet_entry.Project_Task,
                    "Month": data.Month,
                    "Date": current_date,
                    "StartDate": entry.StartDate,
                    "EndDate": entry.EndDate,
                    "WorkDescription": data.Notes or timesheet_entry.Notes,
                    "HoursWorked": hours_worked,
                    "TimesheetAttachmentURL": data.time_sheet_attachment_key,
                    "Status": self.status,
                    "IPAddress": self.request,
                    "Latitude": data.Latitude,
                    "Longitude": data.Longitude,
                    "UpdatedTimeAndDate": None,
                    "RequestedBy": self.token_info["Id"],
                    "TenantUUID": tenantUUID,
                    "ClientUUID": timesheet_entry.Client_Name if data.Timesheet[0].Client_Name != self.customer.ShortName  else None,
                    "VendorName": result_data.get("VendorUUID") if result_data is not None and result_data.get("VendorUUID") else None,
                    "ProjectUUID": timesheet_entry.Project_Name if data.Timesheet[0].Client_Name != self.customer.ShortName else None,
                    "SOWUUID": timesheet_entry.SOW_Name if data.Timesheet[0].Client_Name != self.customer.ShortName else None,
                    "TIMD": TIMD,
                    "TIMN": TIMN,
                },
            ).fetchone()
            self.db.commit()
            timesheet_id = timsheetresult[0]
            if timesheet_entry.Project_Name != "Internal" or timesheet_entry.Project_Task == "Time Off" or timesheet_entry.Client_Name != ShortName:
                week_result = self.db.execute(
                    check_week_query,
                    {"UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                        "CurrentDate": current_date},
                ).fetchone()

                if week_result:
                    # Update existing timesheet week record
                    self.db.execute(
                        update_week_query,
                        {
                            "HoursWorked": hours_worked,
                            "TIMWID": week_result[0],
                            "NewID": timesheet_id,
                            "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                        },
                    )
                else:
                    # Create new timesheet week record
                    TIMW = f"TIMW{int(TIMW[4:]) + 1:06d}"
                    week_start, week_end = self._get_week_start_end(current_date)
                    self.db.execute(
                        insert_query_week,
                        {
                            "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                            "WeekStartDate": week_start,
                            "WeekEndDate": week_end,
                            "TotalHours": hours_worked,
                            "Status": "Pending",
                            "UpdatedTimeAndDate": None,
                            "TenantUUID": tenantUUID,
                            "TIMWID": TIMW,
                            "IDs": [timesheet_id],
                        },
                    )

                    self.db.commit()
                self._update_or_insert_month_record(
                    current_date, hours_worked, ID=timesheet_id
                )
        
        self.send_notification(current_date,data.Company_Portal_Url)
        self.send_notification_hr(current_date, user_uuid)

    def insertweekTIM(self, timesheetWeek):
        
        check_week_query = text(
                f"""
                SELECT "TIMWID", "TotalHours"
                FROM {timesheetWeek}
                WHERE "UserUUID" = :UserUUID
                AND :CurrentDate BETWEEN "WeekStartDate" AND "WeekEndDate"
                """
            )

        update_week_query = text(
                f"""
                UPDATE {timesheetWeek}
                SET "TotalHours" = "TotalHours" + :HoursWorked,
                "IDs" = array_append("IDs", :NewID)
                WHERE "TIMWID" = :TIMWID AND "UserUUID" = :UserUUID
                """
            )

        insert_query_week = text(
                f"""
                INSERT INTO {timesheetWeek} (
                    "UserUUID", "WeekStartDate", "WeekEndDate", "TotalHours",
                    "Status", "UpdatedTimeAndDate", "TenantUUID","TIMWID", "IDs"
                ) VALUES (
                    :UserUUID, :WeekStartDate, :WeekEndDate, :TotalHours,
                    :Status, :UpdatedTimeAndDate, :TenantUUID, :TIMWID, :IDs
                )
                """
            )
        
        return check_week_query,update_week_query,insert_query_week

    def send_notification(self, current_date, Company_Portal_Url):
        print("Sending notification to Admin")
        admins = self._get_all_admins(Company_Portal_Url)
        if isinstance(admins, dict):
            admins = [admins]
        for admin in admins:
            self.notification.create_notification(
                type="Timesheet",
                action="Created",
                to_uuid=str(admin["UserUUID"]),
                from_uuid=self.token_info["Id"],
                date=current_date,
            )
        self.db.commit()
    
    def send_notification_hr(self, current_date, user_uuid):
        try:
            hr_uuid = self.get_assigned_hr(self.company_portal_url, user_uuid)
            if hr_uuid:  # Only send notification if HR is assigned
                self.notification.create_notification(
                    type="Timesheet",
                    action="Created",
                    to_uuid=str(hr_uuid),
                    from_uuid=self.token_info["Id"],    
                    date=current_date,
                )
                self.db.commit()
            else:
                logger.info(f"No HR manager assigned for user {user_uuid}")
        except Exception as e:
            logger.error(f"Error sending HR notification: {str(e)}")
            raise e
            # Don't raise the exception - just log it and continue
            # This prevents notification errors from breaking timesheet creation

    def _check_timesheet_exists(self, time_sheet_table: str, timesheet_id: int):
        check_timesheet_query = text(
            f'SELECT * FROM {time_sheet_table} WHERE "ID" = :timesheet_id AND "UserUUID" = :user_uuid'
        )
        return self.db.execute(
            check_timesheet_query,
            {"timesheet_id": timesheet_id, "user_uuid": self.token_info["Id"]},
        ).fetchone()

    def _get_week_start_end(self, current_date):
        # Calculate the start of the week (Monday)
        week_start = current_date - timedelta(days=current_date.weekday())

        # Calculate the end of the week (Sunday)
        week_end = current_date + timedelta(days=6 - current_date.weekday())

        # Get the first day of the month
        first_day_of_month = current_date.replace(day=1)

        # Get the last day of the current month
        next_month = current_date.replace(day=28) + timedelta(days=4)
        last_day_of_month = next_month - timedelta(days=next_month.day)

        # Adjust week_start if the week crosses into the previous month
        if week_start < first_day_of_month:
            week_start = first_day_of_month

        # Adjust week_end if the week crosses into the next month
        if week_end >= last_day_of_month:
            week_end = last_day_of_month

        return week_start, week_end

    def _get_month_start_end(self, current_date: datetime):
        date_obj = current_date.date()
        start = date_obj.replace(day=1)
        _, last_day = calendar.monthrange(date_obj.year, date_obj.month)
        end = date_obj.replace(day=last_day)
        return start, end

    def _get_TMdata(self):
        shortName = self.customer.ShortName
        SchemaName = self.customer.SchemaName
        time_sheet_table = f"{SchemaName}.tb_{shortName}_timesheet"

        select_query = text(
            f"""
            SELECT "ID", "TIMN", "TIMD" FROM {time_sheet_table}
            WHERE "UserUUID" = :UserUUID
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        select_query_week = text(
            f"""
            SELECT "TIMWID" FROM {SchemaName}.tb_{shortName}_timesheet_week
            WHERE "UserUUID" = :UserUUID
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        select_query_month = text(
            f"""
            SELECT "TIMMID" FROM {SchemaName}.tb_{shortName}_timesheet_month
            WHERE "UserUUID" = :UserUUID
            ORDER BY "ID" DESC LIMIT 1
            """
        )

        result = self.db.execute(
            select_query, {"UserUUID": self.uuid if self.uuid else self.token_info["Id"]})
        TIMdata = result.mappings().first()
        timw = self.db.execute(select_query_week, {
                               "UserUUID": self.uuid if self.uuid else self.token_info["Id"]})
        timw_result = timw.mappings().first()
        timm = self.db.execute(select_query_month, {
                               "UserUUID": self.uuid if self.uuid else self.token_info["Id"]})
        timm_result = timm.mappings().first()

        if timm_result:
            TIMM = timm_result.get("TIMMID")
        else:
            TIMM = "TIMM000000"
        if timw_result:
            TIMW = timw_result.get("TIMWID")
        else:
            TIMW = "TIMW000000"
        if TIMdata is None or TIMdata["TIMN"] is None:
            TIMN = "TIM000001"
        else:
            last_TIM = TIMdata["TIMN"]
            TIM_number = int(re.search(r"\d+", last_TIM).group()) + 1
            TIMN = f"TIMN{TIM_number:06d}"

        TIMD = TIMdata["TIMD"] if TIMdata and TIMdata["TIMD"] else "TIMD000000"
        ID = TIMdata["ID"] if TIMdata and TIMdata["ID"] else 0
        return ID, TIMN, TIMD, TIMM, TIMW

    def _update_or_insert_month_record(
        self, current_date: datetime, hours_worked: float, ID: int
    ):

        timesheetMonth = (
            f"{self.customer.SchemaName}.tb_{
                self.customer.ShortName}_timesheet_month"
        )

        check_month_query = text(
            f"""
            SELECT "TIMMID", "TotalHours"
            FROM {timesheetMonth}
            WHERE "UserUUID" = :UserUUID
            AND DATE_TRUNC('day', :CurrentDate) BETWEEN DATE_TRUNC('day', "MonthStartDate") AND DATE_TRUNC('day', "MonthEndDate")
            """
        )


        month_result = self.db.execute(
            check_month_query,
            {"UserUUID": self.uuid if self.uuid else self.token_info["Id"], "CurrentDate": current_date},
        ).fetchone()

        if month_result:
            # Update existing timesheet month record
            update_month_query = text(
                f"""
                UPDATE {timesheetMonth}
                SET "TotalHours" = "TotalHours" + :HoursWorked, "IDs" = array_append("IDs", :NewID)
                WHERE "TIMMID" = :TIMMID AND "UserUUID" = :UserUUID
                """
            )
            self.db.execute(
                update_month_query,
                {
                    "HoursWorked": hours_worked,
                    "TIMMID": month_result[0],
                    "NewID": ID,
                    "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                },
            )
        else:
            # Create new timesheet month record
            TIMM = f"TIMM{int(self._get_TMdata()[3][4:]) + 1:06d}"
            month_start, month_end = self._get_month_start_end(current_date)
            insert_query_month = text(
                f"""
                INSERT INTO {timesheetMonth} (
                    "UserUUID", "MonthStartDate", "MonthEndDate", "TotalHours",
                    "Status", "UpdatedTimeAndDate", "TenantUUID", "TIMMID", "IDs"
                ) VALUES (
                    :UserUUID, :MonthStartDate, :MonthEndDate, :TotalHours,
                    :Status, :UpdatedTimeAndDate, :TenantUUID, :TIMMID, :IDs
                )
                """
            )
            self.db.execute(
                insert_query_month,
                {
                    "UserUUID": self.uuid if self.uuid else self.token_info["Id"],
                    "MonthStartDate": month_start,
                    "MonthEndDate": month_end,
                    "TotalHours": hours_worked,
                    "Status": "Pending",
                    "UpdatedTimeAndDate": None,
                    "TenantUUID": self._get_tenant(self.company_portal_url),
                    "TIMMID": TIMM,
                    "IDs": [ID],
                },
            )
        self.db.commit()

    def json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, UUID):  
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    def _update_existing_timesheet(self, time_sheet_table: str, data: UpdateTimeSheet):
        first_entry = data.time[0]
        select_query = text(
            f'SELECT * FROM {time_sheet_table} WHERE "ID" = :timesheet_id'
        )
        existing_record = (
            self.db.execute(select_query, {"timesheet_id": data.TimeSheetID})
            .mappings()
            .one()
        )
        sowdata = SOWManager(self.db, self.token_info, self.company_portal_url)
        cdata = ClientManager(self.db, self.token_info, self.company_portal_url)
        pdata = ProjectManager(self.db, self.token_info, self.company_portal_url)
        # Prepare the update data
        update_data = {
            "ClientName": cdata._get_client(clientuuid=data.Client_Name)[0]["ClientName"],
            "ClientUUID": data.Client_Name,
            "ProjectUUID": data.Project_Name,
            "ProjectName": pdata._get_project(projectuuid= data.Project_Name)[0]["ProjectName"],
            "SOWName": sowdata._get_sow(sowuuid =data.SOW_Name)[0]["SOWName"],
            "SOWUUID": data.SOW_Name,
            "User_Manager": data.User_Manager,
            "ProjectBucket": data.Project_Task,
            "Month": data.Month,
            "StartDate": first_entry.StartDate,
            "EndDate": first_entry.EndDate,
            "WorkDescription": data.Notes,
            "HoursWorked": first_entry.HoursWorked,
            "TimesheetAttachmentURL": data.time_sheet_attachment_key,
        }

        fields_updated = []
        fields_values_updated = {}

        print("Here")
        for key, new_value in update_data.items():
            if existing_record[key] != new_value:
                fields_updated.append(key)
                fields_values_updated[key] = {
                    "before": existing_record[key],
                    "after": new_value,
                }

        print("Here")
        # Add FieldsUpdated and FieldsValuesUpdated to the update data
        update_data["FieldsUpdated"] = json.dumps(fields_updated)
        update_data["FieldsValuesUpdated"] = json.dumps(
            fields_values_updated, default=self.json_serial
        )
        print("here")
        update_query = text(
            f"""
            UPDATE {time_sheet_table} SET
                "ClientName" = :ClientName,
                "ClientUUID" = :ClientUUID,
                "ProjectName" = :ProjectName,
                "ProjectUUID" = :ProjectUUID,
                "SOWName" = :SOWName,
                "SOWUUID" = :SOWUUID,
                "User_Manager" = :User_Manager,
                "ProjectBucket" = :ProjectBucket,
                "Month" = :Month,
                "StartDate" = :StartDate,
                "EndDate" = :EndDate,
                "WorkDescription" = :WorkDescription,
                "HoursWorked" = :HoursWorked,
                "TimesheetAttachmentURL" = :TimesheetAttachmentURL,
                "FieldsUpdated" = :FieldsUpdated,
                "FieldsValuesUpdated" = :FieldsValuesUpdated,
                "UpdatedTimeAndDate" = CURRENT_TIMESTAMP

            WHERE "ID" = :timesheet_id
            """
        )

        result = self.db.execute(
            update_query, {**update_data, "timesheet_id": data.TimeSheetID}
        )
        self.db.commit()

        if result.rowcount > 0:
            date = first_entry.StartDate
            new_hours = first_entry.HoursWorked
            old_hours = existing_record["HoursWorked"]
            hours_difference = float(new_hours) - float(old_hours)
            self._update_timesheet_week_old(date, hours_difference)
            self._update_timesheet_month_old(date, hours_difference)

    def _update_timesheet_week_old(self, date, hours_difference):
        SchemaName, ShortName = self._get_company_info(self.company_portal_url)
        timesheetWeek = f"{SchemaName}.tb_{ShortName}_timesheet_week"

        update_week_query = text(
            f"""
            UPDATE {timesheetWeek}
            SET "TotalHours" = GREATEST("TotalHours" + :hours_difference, 0),
                "UpdatedTimeAndDate" = CURRENT_TIMESTAMP
            WHERE "UserUUID" = :UserUUID
            AND :Date BETWEEN "WeekStartDate" AND "WeekEndDate"
            """
        )

        self.db.execute(
            update_week_query,
            {
                "UserUUID": self.token_info["Id"],
                "hours_difference": hours_difference,
                "Date": date,
            },
        )
        self.db.commit()

    def _update_timesheet_month_old(self, current_date: datetime, hours_worked: float):
        SchemaName, ShortName = self._get_company_info(self.company_portal_url)
        timesheetMonth = f"{SchemaName}.tb_{ShortName}_timesheet_month"

        update_month_query = text(
            f"""
            UPDATE {timesheetMonth}
            SET "TotalHours" = "TotalHours" + :HoursWorked,
                "UpdatedTimeAndDate" = CURRENT_TIMESTAMP
            WHERE "UserUUID" = :UserUUID
            AND :CurrentDate BETWEEN "MonthStartDate" AND "MonthEndDate"
            """
        )

        self.db.execute(
            update_month_query,
            {
                "UserUUID": self.token_info["Id"],
                "HoursWorked": hours_worked,
                "CurrentDate": current_date,
            },
        )
        self.db.commit()

    def _update_timesheet_week(self, useruuid, date, hours_difference, timesheet_ids):
        SchemaName, ShortName = self._get_company_info(self.company_portal_url)
        timesheetWeek = f"{SchemaName}.tb_{ShortName}_timesheet_week"

        update_week_query = text(
            f"""
            UPDATE {timesheetWeek}
            SET "TotalHours" = GREATEST("TotalHours" + :hours_difference, 0),
                "UpdatedTimeAndDate" = CURRENT_TIMESTAMP,
                "IDs" = array_remove("IDs", t.id)
            FROM (SELECT UNNEST(:timesheet_ids) AS id) t
            WHERE "UserUUID" = :UserUUID
            AND :Date BETWEEN "WeekStartDate" AND "WeekEndDate"
            RETURNING "TotalHours"
            """
        )

        result = self.db.execute(
            update_week_query,
            {
                "UserUUID": useruuid,
                "hours_difference": hours_difference,
                "Date": date,
                "timesheet_ids": timesheet_ids,
            },
        ).mappings().all()
        print("REsult", result)
        select_query = text(
            f"""
            SELECT "TotalHours"
            FROM {timesheetWeek}
            WHERE "UserUUID" = :UserUUID
            AND :Date BETWEEN "WeekStartDate" AND "WeekEndDate"
            """
        )
        results = self.db.execute(
            select_query,
            {
                "UserUUID": useruuid,
                "Date": date,
            },
        ).mappings().all()
        if not results:
            print("No timesheet weeks found for the given date.")

        else:
            for result in results:
                if result["TotalHours"] == 0:
                    delete_query = text(
                        f"""
                        DELETE FROM {timesheetWeek}
                        WHERE "TotalHours" = 0
                        AND "UserUUID" = :UserUUID
                        AND :Date BETWEEN "WeekStartDate" AND "WeekEndDate"
                        """
                    )
                    self.db.execute(
                        delete_query,
                        {
                            "UserUUID": useruuid,
                            "Date": date,
                        }
                    )
                    self.db.commit()

        # if result["TotalHours"] == 0:
        #     delete_query = text(
        #         f"""
        #             DELETE FROM {timesheetWeek}
        #             WHERE "TotalHours" = 0
        #             AND "UserUUID" = :UserUUID
        #             AND :Date BETWEEN "WeekStartDate" AND "WeekEndDate"
        #             """
        #     )
        #     self.db.execute(
        #         delete_query,
        #         {
        #             "UserUUID": useruuid,
        #             "Date": date,
        #         }
        #     )
        #     self.db.commit()


    def _update_timesheet_month(
        self, useruuid, current_date: datetime, hours_worked: float, timesheet_ids
    ):
        SchemaName, ShortName = self._get_company_info(self.company_portal_url)
        timesheetMonth = f"{SchemaName}.tb_{ShortName}_timesheet_month"

        update_month_query = text(
            f"""
            UPDATE {timesheetMonth}
            SET "TotalHours" = "TotalHours" + :HoursWorked,
                "UpdatedTimeAndDate" = CURRENT_TIMESTAMP,
                "IDs" = array_remove("IDs", t.id)
            FROM (SELECT UNNEST(:timesheet_ids) AS id) t
            WHERE "UserUUID" = :UserUUID
            AND :CurrentDate BETWEEN "MonthStartDate" AND "MonthEndDate"
            RETURNING "TotalHours"
            """
        )

        month_result = self.db.execute(
            update_month_query,
            {
                "UserUUID": useruuid,
                "HoursWorked": hours_worked,
                "CurrentDate": current_date,
                "timesheet_ids": timesheet_ids,
            },
        ).mappings().all()
        print(month_result)
        self.db.commit()

        for row in month_result:
            if row["TotalHours"] == 0:
                delete_query = text(
                    f"""
                    DELETE FROM {timesheetMonth}
                    WHERE "TotalHours" = 0
                    AND "UserUUID" = :UserUUID
                    AND :Date BETWEEN "MonthStartDate" AND "MonthEndDate"
                    """
                )
                self.db.execute(
                    delete_query,
                    {
                        "UserUUID": useruuid,
                        "Date": current_date,
                    }
                )
                self.db.commit()

    def _create_additional_timesheets(
        self, time_sheet_table: str, data: UpdateTimeSheet
    ):
        for entry in data.time[1:]:
            if entry.StartDate > entry.EndDate:
                raise HTTPException(
                    status_code=400, detail="StartDate cannot be after EndDate"
                )

            distributed_hours_per_day = self._distribute_hours(
                entry.StartDate, entry.EndDate, entry.HoursWorked
            )

            current_date = entry.StartDate
            while current_date <= entry.EndDate:
                self._insert_timesheet_entry(
                    time_sheet_table,
                    data,
                    entry,
                    current_date,
                    distributed_hours_per_day,
                )
                current_date += timedelta(days=1)

    def _delete_timesheets(self, time_sheet_table: str, timesheet_ids: List[int]):

        fetch_query = text(
            f"""
            SELECT "UserUUID", "ID", "StartDate", "HoursWorked"
            FROM {time_sheet_table}
            WHERE "ID" IN :TimeSheet_Ids
            """
        )
        result = self.db.execute(
            fetch_query,
            {"TimeSheet_Ids": tuple(timesheet_ids)},
        )
        timesheets_to_delete = result.mappings().all()
        print("timdel----", timesheets_to_delete)
        
        delete_query = text(
            f"""
            DELETE FROM {time_sheet_table}
            WHERE "ID" IN :TimeSheet_Ids
            """
        )
        self.db.execute(
            delete_query,
            {"TimeSheet_Ids": tuple(timesheet_ids)},
        )
        print("errorrr")
        for timesheet in timesheets_to_delete:
            print(timesheet["HoursWorked"])
            self._update_timesheet_week(
               timesheet.UserUUID, timesheet.StartDate, -timesheet.HoursWorked, [timesheet.ID]
            )
            self._update_timesheet_month(
                timesheet.UserUUID, timesheet.StartDate, -timesheet.HoursWorked, [timesheet.ID]
            )
        self.db.commit()

    def _handle_exception(self, exception):
        self.db.rollback()
        if isinstance(exception, HTTPException):
            raise exception
        logger.error(f"Error occurred: {str(exception)}")
        raise HTTPException(
            status_code=500, detail="An error occurred while processing the request."
        )
