from decimal import Decimal
import logging
import re
import uuid
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request, logger
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from App.Models.Classes.SOWManager import SOWManager
from App.Models.Classes.ClientManager import ClientManager
from App.Models.Classes.ProjectManager import ProjectManager
from App.Models.Classes.TimesheetManager import CreateTimeSheetManager
from App.Models.Classes.token_authentication import encrypt_data
from App.Models.Classes.TenantSettings import TenantSettingsManager
from App.Models.Classes.GetUser import GetUser
from App.Models.Classes.Notification import ManageNotification
from Models.utils.send_mail import send_mail
from Models.db import models
from Models.db.schemas import DeleteRequest, RequestSchema, UpdateRequestSchema, BritsUserBGVUpdateSchema
from App.Models.Classes.userbgvManager import UserBGVManager
import sys
import os
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)




class RequestManager:
    def __init__(self, db: Session, token_info: Dict, request:Request =None):
        self.db = db
        self.token_info = token_info
        self.customer = None
        self.Company_Portal_Url = None
        self.admin = None
        self.request = request

    def _get_admin(self, Company_Portal_Url):
        print(self.Company_Portal_Url, "------")
        if Company_Portal_Url is not None:
            user = self.get_tenant_info(Company_Portal_Url)
            user_table_name = f"{user.SchemaName}.tb_{
                user.ShortName}_user_info"
            select_query = text(f"""
                SELECT "UserUUID", "Role"
                FROM {user_table_name}
                WHERE "Role" IN ('Admin', 'Manager')
            """)

            result = self.db.execute(select_query).mappings().all()
            return result
        return None

    def get_tenant_info(self, company_portal_url: str):
        self.Company_Portal_Url = company_portal_url
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        self.customer = user
        if user is None:
            return error.error("Schema not found", 404, "Tenant Info")
        return user

    def json_serial(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    def _get_tenant(self, Company_portal_Url):
        self.Company_Portal_Url = Company_portal_Url
        user = self.get_tenant_info(Company_portal_Url)
        tenant_table = f"{user.SchemaName}.tb_{user.ShortName}_tenant_info"
        select_query = text(
            f"""
            SELECT "TenantUUID" from {tenant_table}
            """
        )
        result = self.db.execute(select_query)
        tenant = result.mappings().one()
        return tenant.get("TenantUUID")

    def _notification(self, data):
        notification = ManageNotification(self.db, self.customer)
        notification.create_notification(
            type=data["type"],
            action=data["action"],
            to_uuid=data["to_uuid"],
            from_uuid=data["from_uuid"],
            date=datetime.now().isoformat(),
            retype=data["retype"],
        )
        self.db.commit()
    
    def send_notification_hr(self, company_portal_url, current_date, user_uuid):
        try:
            notification = ManageNotification(self.db, self.customer)
            print("-----------------------------\n")
            print("user_uuid", user_uuid)
            print("company_portal_url", company_portal_url)
            timesheet_manager = CreateTimeSheetManager(self.db, self.token_info, company_portal_url)
            hr_uuid = timesheet_manager.get_assigned_hr(company_portal_url, user_uuid)
            if hr_uuid:
                notification.create_notification(
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

    async def create_request(self, data: RequestSchema):
        GetUser(self.db, data.Company_Portal_Url).verify_user(self.token_info)
        try:
            self.Company_Portal_Url = data.Company_Portal_Url
            print(self.Company_Portal_Url, "portal----")
            user = self.get_tenant_info(data.Company_Portal_Url)
            company_schema_name = user.SchemaName
            company_shortname = user.ShortName

            if data.RequestType == "TimeSheet":
                return self.create_timesheet_request(
                    data, company_schema_name, company_shortname
                )
            else:
                return await self.create_other_request(
                    data, company_schema_name, company_shortname
                )

        except HTTPException as http_exc:
            raise http_exc
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(sql_exc)}")
            raise sql_exc
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e


    def create_timesheet_request(
        self, data: RequestSchema, company_schema_name: str, company_shortname: str
    ):
        request_table = f"{company_schema_name}.tb_{
            company_shortname}_requests"
        insert_query = text(
            f"""
            INSERT INTO {request_table} ("REQN", "UserUUID", "RequestUUID", "RequestType", "RequestDetails",
            "RequestDescription", "RequestPriority", "RequestStatus", "RequestAttachmentURL", "UpdatedTimeAndDate", "RequestedBy", "TenantUUID")
            VALUES (:REQN, :UserUUID, :RequestUUID, :RequestType, :RequestDetails,
            :RequestDescription, :RequestPriority, :RequestStatus, :RequestAttachmentURL, :UpdatedTimeAndDate, :RequestedBy, :TenantUUID)
            """
        )
        tenantUUID = self._get_tenant(data.Company_Portal_Url)

        for timesheet_entry in data.Timesheet:
            for time_entry in timesheet_entry.time:
                start_date = datetime.fromisoformat(str(time_entry.StartDate))
                end_date = datetime.fromisoformat(str(time_entry.EndDate))
                hours_worked = time_entry.HoursWorked

                request_details = {
                    "Client": timesheet_entry.Client_Name,
                    "Project": timesheet_entry.Project_Name,
                    "Task": timesheet_entry.Project_Task,
                    "Time": [
                        {
                            "StartDate": start_date.isoformat(),
                            "EndDate": end_date.isoformat(),
                            "Hours": hours_worked,
                        }
                    ],
                    "IPAddress": timesheet_entry.IPAddress,
                    "Longitude": timesheet_entry.Longitude,
                    "Latitude": timesheet_entry.Latitude,
                }

                REQN = self._get_REQdata(data.Company_Portal_Url)
                print(REQN)
                self.db.execute(
                    insert_query,
                    {
                        "REQN": REQN,
                        "UserUUID": self.token_info["Id"],
                        "RequestUUID": str(uuid.uuid4()),
                        "RequestType": data.RequestType,
                        "RequestDetails": json.dumps(request_details),
                        "RequestDescription": data.RequestDescription,
                        "RequestPriority": data.RequestPriority,
                        "RequestStatus": "Pending",
                        "RequestAttachmentURL": data.RequestAttachmentURL,
                        "UpdatedTimeAndDate": None,
                        "RequestedBy": self.token_info["Id"],
                        "TenantUUID": tenantUUID,
                    },
                )

                self.db.commit()
                admins = self._get_admin(self.Company_Portal_Url)
                if isinstance(admins, dict):
                    admins = [admins]
                for admin in admins:
                    notData = {
                        "to_uuid": admin.get("UserUUID"),
                        "from_uuid": self.token_info["Id"],
                        "type": "Request",
                        "action": "Created",
                        "date": datetime.now().isoformat(),
                        "retype": data.RequestType,
                    }
                    self._notification(notData)
                self.send_notification_hr(data.Company_Portal_Url, datetime.now().isoformat(), self.token_info["Id"])
            
        return JSONResponse(
            status_code=201, content={"message": "Request created successfully"}
        )

    def _get_REQdata(self, Company_Portal_Url):
        user = self.get_tenant_info(Company_Portal_Url)
        requestTable = f"{user.SchemaName}.tb_{user.ShortName}_requests"

        select_query = text(
            f"""
            SELECT "REQN" from {requestTable}
            WHERE "UserUUID" = :UserUUID
            ORDER BY "ID" DESC LIMIT 1
            """
        )
        result = self.db.execute(
            select_query, {"UserUUID": self.token_info["Id"]})
        reqn = result.mappings().first()

        if reqn is None or reqn.get("REQN") is None:
            REQN = "REQN000001"
        else:
            last_reqn = reqn.get("REQN")
            reqn_number = int(last_reqn[4:]) + 1
            REQN = f"REQN{str(reqn_number).zfill(6)}"

        return REQN

    async def create_other_request(
        self, data: RequestSchema, company_schema_name: str, company_shortname: str
    ):
        try:
            print("here1")
            (
                request_type,
                request_details,
                request_description,
                request_priority,
                request_attachment_url,
            ) = self.prepare_request_data(data)
            print("here2")
            request_table = f"{company_schema_name}.tb_{
                company_shortname}_requests"
            user_table = f"{company_schema_name}.tb_{
                    company_shortname}_user_info"
            insert_query = text(
                f"""
                INSERT INTO {request_table} ("REQN", "UserUUID", "RequestUUID", "RequestType", "RequestDetails",
                "RequestDescription", "RequestPriority", "RequestStatus","RequestAttachmentURL", "UpdatedTimeAndDate", "RequestedBy", "TenantUUID")
                VALUES (:REQN, :UserUUID, :RequestUUID, :RequestType, :RequestDetails,
                :RequestDescription, :RequestPriority, :RequestStatus, :RequestAttachmentURL, :UpdatedTimeAndDate, :RequestedBy, :TenantUUID)
                """
            )
            tenantUUID = self._get_tenant(data.Company_Portal_Url)
            print("here3")
            REQN = self._get_REQdata(data.Company_Portal_Url)
            print(REQN, "here4")
            if data.RequestType == "ProfileChange" and isinstance(request_details, BaseModel):
                request_details = request_details.dict()
            self.db.execute(
                insert_query,
                {
                    "REQN": REQN,
                    "UserUUID": self.token_info["Id"],
                    "RequestUUID": str(uuid.uuid4()),
                    "RequestType": request_type,
                    "RequestDetails": json.dumps(request_details),
                    "RequestDescription": request_description,
                    "RequestPriority": request_priority,
                    "RequestStatus": "Pending",
                    "RequestAttachmentURL": request_attachment_url,
                    "RequestedBy": self.token_info["Id"],
                    "TenantUUID": tenantUUID,
                    "UpdatedTimeAndDate": None,
                },
            )
            self.db.commit()
            admins = self._get_admin(self.Company_Portal_Url)
            if isinstance(admins, dict):
                admins = [admins]

            for admin in admins:
                notification_data = {
                    "to_uuid": admin.get("UserUUID"),
                    "from_uuid": self.token_info["Id"],
                    "type": "Request",
                    "action": "Created",
                    "date": datetime.now().isoformat(),
                    "retype": request_type,  # Assuming request_type is an instance variable
                }
                self._notification(notification_data)
            self.send_notification_hr(data.Company_Portal_Url, datetime.now().isoformat(), self.token_info["Id"])
            # Send email notification to the admin
            tenant_settings_manager = TenantSettingsManager(self.db, data.Company_Portal_Url)
            if await tenant_settings_manager.is_request_notification_enabled():
                user_details = self.db.execute(text(f"SELECT \"FirstName\", \"LastName\" FROM {user_table} WHERE \"UserUUID\" = :UserUUID"), {"UserUUID": self.token_info["Id"]}).fetchone()
                user_name = f"{user_details.FirstName} {user_details.LastName}"
                admin_details = self.db.execute(text(f"SELECT \"Email\", \"FirstName\", \"LastName\" FROM {user_table} WHERE \"Role\" = 'Admin'")).fetchall()
                # Ensure data.startDate is handled correctly
                if isinstance(data.startDate, list):
                    formatted_range = ", ".join(
                        [date.strftime("%B-%d-%Y").lower() for date in data.startDate]
                    )
                else:
                    formatted_range = data.startDate.strftime('%B %d, %Y')
                for admin in admin_details:
                    admin_name = f"{admin[1]} {admin[2]}" if admin[1] and admin[2] else "System Admin"
                    try:
                        send_mail(
                            admin[0],
                            user_name,
                            admin[2],
                            "Request Notification Admin",
                            data.Company_Portal_Url,
                            "request",
                            "created",
                            admin_name,
                            formatted_range,
                            f"{request_type} Request",
                            request_type,
                        )
                    except Exception as e:
                        print(f"Error sending email at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                        raise HTTPException(status_code=500, detail="An error occurred while sending the email.")
            
            
            return JSONResponse(
                status_code=201, content={"message": "Request created successfully"}
            )
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e

    def prepare_request_data(self, data: RequestSchema):
        if data.RequestType == "HR":
            return (
                "HR",
                {"RequestType": data.Type},
                data.RequestDescription,
                data.RequestPriority,
                None,
            )
        elif data.RequestType == "TimeOff":
            start_date, end_date = self.validate_dates(
                data.startDate[0], data.endDate[0]
            )
            number_of_days = (end_date - start_date).days + 1
            return (
                "TimeOff",
                {
                    "Days": number_of_days,
                    "Reason": data.RequestDescription,
                    "LeaveType": data.Type,
                    "StartDate": start_date.isoformat(),
                    "EndDate": end_date.isoformat(),
                    "Hours": data.Hours[0],
                },
                None,
                None,
                None,
            )
        elif data.RequestType == "ProfileChange":
            return (
                "ProfileChange",
                data.ProfileUpdate,
                data.RequestDescription,
                data.RequestPriority,
                data.RequestAttachmentURL,
            )
        elif data.RequestType == "Access":
            return (
                "Access",
                {"Access": data.Type},
                data.RequestDescription,
                data.RequestPriority,
                None,
            )
        else:
            return error.error("Invalid RequestType", 400, "Invalid RequestType")

    def validate_dates(self, start_date, end_date):
        if not (isinstance(start_date, datetime) and isinstance(end_date, datetime)):
            return error.error("Invalid or missing startDate or endDate", 400, "Invalid Dates")
        return start_date, end_date

    def get_requests(
        self,
        company_portal_url: str,
        request_type: Optional[str] = None,
        user_uuids: Optional[List[str]] = None,
        path_suffix: str = None,
        pagenum: Optional[int] = None,
        own: Optional[int] = None,
        sortBy: Optional[str] = None,
        order: Optional[int] = 1,
        Status: Optional[str] = None,
    ):
        GetUser(self.db, company_portal_url).verify_user(self.token_info)
        try:
            user = self.get_tenant_info(company_portal_url)
            company_schema_name = user.SchemaName
            company_shortname = user.ShortName

            request_table = f"{company_schema_name}.tb_{
                company_shortname}_requests"
            user_table = f"{company_schema_name}.tb_{
                company_shortname}_user_info"

            sortable_columns = {
                "CreatedOn": 'r."CreationTimeAndDate"',
                "RequestType": 'r."RequestType"',
                "RequestPriority": 'r."RequestPriority"',
                "RequestStatus": 'r."RequestStatus"',
                "RequesterName": 'u."FirstName"',
                "ApproverName": 'a."FirstName"',
            }

            # Get the actual DB column to sort by or use default
            sort_column = sortable_columns.get(sortBy, 'r."CreationTimeAndDate"')
            direction = "ASC" if order == 1 else "DESC"

            query_str = f"""
                SELECT r."ID", r."REQN", r."RequestUUID", r."RequestType", r."RequestDetails", r."RequestDescription",
                    r."RequestPriority", r."RequestStatus", r."RequestAttachmentURL", r."CreationTimeAndDate",
                    r."ApprovedBy", a."FirstName" as "ApproverFirstName", a."LastName" as "ApproverLastName",
                    r."UserUUID", u."FirstName" as "RequesterFirstName", u."LastName" as "RequesterLastName"
                FROM {request_table} r
                JOIN {user_table} u ON r."UserUUID" = u."UserUUID"
                LEFT JOIN {user_table} a ON r."ApprovedBy" = a."UserUUID" 

            """



            params = {}
            where_clauses = []
            print("path_suffix", path_suffix)
            if Status:
                where_clauses.append("""
                    r."RequestStatus" = :status
                """)
                params["status"] = Status
            
            if path_suffix == "TIM":
                print("herepath")
                where_clauses.append("""
                    CAST(r."RequestDetails"->>'StartDate' AS TIMESTAMP) >= date_trunc('week', CURRENT_DATE) + interval '1 day'
                    AND CAST(r."RequestDetails"->>'EndDate' AS TIMESTAMP) < date_trunc('week', CURRENT_DATE) + interval '8 days'
                    AND r."RequestStatus" IN ('Pending', 'Approved')
                """)
            
            if path_suffix == "REQTOF":
                where_clauses.append("""
                    CAST(r."RequestDetails"->>'StartDate' AS TIMESTAMP) >= date_trunc('month', CURRENT_DATE) - interval '2 months'
                    AND CAST(r."RequestDetails"->>'EndDate' AS TIMESTAMP) <= date_trunc('month', CURRENT_DATE) + interval '1 month' - interval '1 day'
                    AND r."RequestStatus" IN ('Pending', 'Approved')
                """)

                
            if path_suffix == "REQTIM":
                where_clauses.append("""
                    EXISTS (
                        SELECT 1 
                        FROM jsonb_array_elements(CAST(r."RequestDetails" AS JSONB)->'Time') AS time_entry
                        WHERE 
                            CAST(time_entry->>'StartDate' AS TIMESTAMP) >= date_trunc('day', CURRENT_DATE) - interval '2 months'
                            AND CAST(time_entry->>'EndDate' AS TIMESTAMP) <= CURRENT_DATE
                    )
                    AND r."RequestStatus" IN ('Pending', 'Approved')
                """)


            # Check user role
            user_role = self.token_info.get("role")
            user_uuid = self.token_info["Id"]


            if user_role == "Admin":
                if user_uuids:
                    where_clauses.append('r."UserUUID" IN :UserUUIDs')
                    params["UserUUIDs"] = tuple(user_uuids)
                elif own ==1:
                    where_clauses.append('r."UserUUID" = :UserUUID')
                    params["UserUUID"] = user_uuid

            elif user_role == "HR":
                if own == 1:
                    where_clauses.append('r."UserUUID" = :UserUUID')
                    params["UserUUID"] = user_uuid
                else:
                    # Fetch all users managed by this HR
                    managed_users_query = f"""
                        SELECT "UserUUID" FROM {user_table}
                        WHERE "HR_Manager" = :HRUUID
                    """
                    managed_users_result = self.db.execute(
                        text(managed_users_query), {"HRUUID": user_uuid})
                    managed_user_uuids = [row[0] for row in managed_users_result]

                    if not managed_user_uuids:
                        # Ensure the query doesn't return anything
                        where_clauses.append("FALSE")
                    else:
                        where_clauses.append('r."UserUUID" IN :ManagedUserUUIDs')
                        params["ManagedUserUUIDs"] = tuple(managed_user_uuids)

                    hr_allowed_types = ("HR", "Access", "ProfileChange", "TimeOff")
                    where_clauses.append('r."RequestType" IN :AllowedTypes')
                    params["AllowedTypes"] = hr_allowed_types


            elif user_role == "Manager":
                if own == 1:
                    where_clauses.append('r."UserUUID" = :UserUUID')
                    params["UserUUID"] = user_uuid
                else:
                    managed_users_query = f"""
                        SELECT "UserUUID" FROM {user_table}
                        WHERE "User_manager" = :ManagerUUID
                    """
                    managed_users_result = self.db.execute(
                        text(managed_users_query), {"ManagerUUID": user_uuid})
                    managed_user_uuids = [row[0] for row in managed_users_result]

                    where_clauses.append('r."UserUUID" IN :ManagedUserUUIDs')
                    params["ManagedUserUUIDs"] = tuple(managed_user_uuids)
            else:
                # Regular user
                where_clauses.append('r."UserUUID" = :UserUUID')
                params["UserUUID"] = user_uuid

            if request_type:
                where_clauses.append('r."RequestType" = :RequestType')
                params["RequestType"] = request_type

            # Add WHERE clause if there are any conditions
            if where_clauses:
                query_str += " WHERE " + " AND ".join(where_clauses)

            # Add the order by clause
            query_str += ' ORDER BY ' + sort_column + ' ' + direction

            query = text(query_str)
            result = self.db.execute(query, params)
            rows = result.mappings().all()
            
            cdata = ClientManager(self.db, self.token_info, company_portal_url)
            pdata = ProjectManager(self.db, self.token_info, company_portal_url)
            requests = [
                {
                    "ID": row["ID"],
                    "REQN": row["REQN"],
                    "RequestType": row["RequestType"],
                    "RequestDetails": {
                    **row["RequestDetails"],
                    "Client": cdata._get_client(clientuuid=row["RequestDetails"]["Client"])[0]["ClientName"],
                    "ClientUUID": row["RequestDetails"]["Client"],
                    "Project": pdata._get_project(projectuuid=row["RequestDetails"]["Project"])[0]["ProjectName"],
                    "ProjectUUID": row["RequestDetails"]["Project"]
                    } if row["RequestType"] == 'TimeSheet' else row["RequestDetails"],
                    "RequestDescription": row["RequestDescription"],
                    "RequestPriority": row["RequestPriority"],
                    "RequestStatus": row["RequestStatus"],
                    "CreatedOn": row["CreationTimeAndDate"],
                    "RequestAttachmentURL": row["RequestAttachmentURL"],
                    "ApproverName": f"{row['ApproverFirstName'] or ''} {row['ApproverLastName'] or ''}".strip() or None,
                    "RequesterName": f"{row['RequesterFirstName'] or ''} {row['RequesterLastName'] or ''}".strip(),
                    "UserUUID": row["UserUUID"],
                }
                for row in rows
            ]
            
            if requests not in ["", []] and ( (user_role in ["Admin","Manager", "HR"] and own != 1)):
                print("---Condition met---")
                # Group requests by user name for admin and manager
                grouped_requests = {}
                for request in requests:
                    requester_name = request["RequesterName"]
                    if requester_name not in grouped_requests:
                        grouped_requests[requester_name] = []
                    grouped_requests[requester_name].append(request)
                result_data = grouped_requests
            else:
                # Return the list of requests for non-admin users
                result_data = requests

            # result_data = requests
            
            if pagenum is not None:
                if pagenum is None or pagenum == 0:
                    pagenum = 1
                pagesize = 10
                
                # Apply pagination to the result_data
                if isinstance(result_data, dict):
                    # For grouped requests, we need to handle pagination differently
                    totalitems = sum(len(items) for items in result_data.values())
                    page_count = (totalitems // pagesize) + (1 if totalitems % pagesize > 0 else 0)
                    
                    # Flatten the grouped data for pagination
                    all_items = []
                    for items in result_data.values():
                        all_items.extend(items)
                    
                    # Apply pagination
                    start_idx = (pagenum - 1) * pagesize
                    end_idx = start_idx + pagesize
                    paginated_items = all_items[start_idx:end_idx]
                    
                    # Re-group the paginated items
                    paginated_grouped = {}
                    for item in paginated_items:
                        requester_name = item["RequesterName"]
                        if requester_name not in paginated_grouped:
                            paginated_grouped[requester_name] = []
                        paginated_grouped[requester_name].append(item)
                    
                    result = paginated_grouped
                else:
                    # For non-grouped requests
                    totalitems = len(result_data)
                    page_count = (totalitems // pagesize) + (1 if totalitems % pagesize > 0 else 0)
                    
                    start_idx = (pagenum - 1) * pagesize
                    end_idx = start_idx + pagesize
                    result = result_data[start_idx:end_idx]
                
                item = {"items": totalitems, "page": page_count}
                data = {"data": result, "total": item}
                return data
            
            return result_data

        except HTTPException as http_exc:
            raise http_exc
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(sql_exc)}")
            raise sql_exc
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e

    def update_request(self, data: UpdateRequestSchema, id: int):
        GetUser(self.db, data.Company_Portal_Url).verify_user(self.token_info)
        try:
            print("here")
            user = self.get_tenant_info(data.Company_Portal_Url)
            company_schema_name = user.SchemaName
            company_shortname = user.ShortName

            request_table = f"{company_schema_name}.tb_{
                company_shortname}_requests"

            existing_request = self.get_existing_request(request_table, id)
            if not existing_request:
                raise HTTPException(
                    status_code=404, detail="Request not found")
            print("here1")
            if data.RequestType == "TimeSheet":
                return self.update_timesheet_request(data, id, request_table)
            else:
                return self.update_other_request(
                    data, id, existing_request, request_table
                )

        except HTTPException as http_exc:
            raise http_exc
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(sql_exc)}")
            raise sql_exc
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e

    def get_existing_request(
        self,
        request_table: str,
        id: Optional[int] = None,
        request_ids: Optional[List[int]] = None,
    ):
        if self.token_info["role"] in ["Admin", "Manager", "HR"]:
            select_query = text(
                f"""
                SELECT "ID", "RequestStatus", "UserUUID", "CreationTimeAndDate", "RequestType", "RequestDetails","RequestDescription", "RequestAttachmentURL"
                FROM {request_table}
                WHERE "ID" = ANY(:IDs)
                """
            )
        else:
            select_query = text(
                f'SELECT * FROM {request_table} WHERE "ID" = :ID AND "UserUUID" = :UserUUID'
            )
        existing_request = self.db.execute(
            select_query,
            {"ID": id, "UserUUID": self.token_info["Id"], "IDs": [
                request_ids]},
        )
        return existing_request.mappings().all()

    def update_timesheet_request(
        self, data: UpdateRequestSchema, id: int, request_table: str
    ):
        existing_request_query = text(
            f'SELECT * FROM {request_table} WHERE "ID" = :ID')
        existing_request = (
            self.db.execute(existing_request_query, {
                            "ID": id}).mappings().first()
        )

        existing_request_dict = existing_request

        fields_updated = []
        fields_values_updated = {}
        update_query = text(
            f"""
            UPDATE {request_table}
            SET "RequestType" = :RequestType, "RequestDetails" = :RequestDetails,
                "RequestDescription" = :RequestDescription, "RequestPriority" = :RequestPriority,"RequestAttachmentURL" = :RequestAttachmentURL,
                "FieldsUpdated" = :FieldsUpdated,
                "FieldsValuesUpdated" = :FieldsValuesUpdated, "UpdatedTimeAndDate" = CURRENT_TIMESTAMP
            WHERE "ID" = :ID
            """
        )

        insert_query = text(
            f"""
            INSERT INTO {request_table} ("UserUUID", "RequestUUID", "RequestType", "RequestDetails",
            "RequestDescription", "RequestPriority", "RequestStatus", "RequestAttachmentURL",
            "UpdatedTimeAndDate", "RequestedBy", "TenantUUID")
            VALUES (:UserUUID, :RequestUUID, :RequestType, :RequestDetails,
            :RequestDescription, :RequestPriority, :RequestStatus, :RequestAttachmentURL,
            :UpdatedTimeAndDate, :RequestedBy, :TenantUUID)
            """
        )

        is_first_iteration = True
        tenantUUID = self._get_tenant(data.Company_Portal_Url)

        for start_date, end_date, total_hours in zip(
            data.startDate or [], data.endDate or [], data.Hours or []
        ):
            start_date, end_date = self.validate_dates(start_date, end_date)
            num_days = (end_date - start_date).days + 1
            hours_per_day = round(total_hours / num_days, 2)

            current_date = start_date
            while current_date <= end_date:
                request_details = {
                    "Client": data.ClientName,
                    "Project": data.ProjectName,
                    "Task": data.Task,
                    "Time": [
                        {
                            "StartDate": current_date.isoformat(),
                            "EndDate": current_date.isoformat(),
                            "Hours": hours_per_day,
                        }
                    ],
                }

                if is_first_iteration:
                    if existing_request_dict["RequestType"] != "TimeSheet":
                        fields_updated.append("RequestType")
                        fields_values_updated["RequestType"] = {
                            "before": existing_request_dict["RequestType"],
                            "after": "TimeSheet",
                        }

                    if existing_request_dict["RequestDetails"] != json.dumps(
                        request_details
                    ):
                        fields_updated.append("RequestDetails")
                        fields_values_updated["RequestDetails"] = {
                            "before": existing_request_dict["RequestDetails"],
                            "after": json.dumps(request_details),
                        }

                    if (
                        existing_request_dict["RequestDescription"]
                        != data.RequestDescription
                    ):
                        fields_updated.append("RequestDescription")
                        fields_values_updated["RequestDescription"] = {
                            "before": existing_request_dict["RequestDescription"],
                            "after": data.RequestDescription,
                        }

                    if (
                        existing_request_dict["RequestAttachmentURL"]
                        != data.RequestAttachmentURL
                    ):
                        fields_updated.append("RequestAttachmentURL")
                        fields_values_updated["RequestAttachmentURL"] = {
                            "before": existing_request_dict["RequestAttachmentURL"],
                            "after": data.RequestAttachmentURL,
                        }
                    self.db.execute(
                        update_query,
                        {
                            "ID": id,
                            "RequestType": "TimeSheet",
                            "RequestDetails": json.dumps(request_details),
                            "RequestDescription": data.RequestDescription,
                            "RequestPriority": None,
                            "RequestAttachmentURL": data.RequestAttachmentURL,
                            "FieldsUpdated": json.dumps(fields_updated),
                            "FieldsValuesUpdated": json.dumps(fields_values_updated),
                        },
                    )

                    is_first_iteration = False
                else:
                    self.db.execute(
                        insert_query,
                        {
                            "UserUUID": self.token_info["Id"],
                            "RequestUUID": str(uuid.uuid4()),
                            "RequestType": "TimeSheet",
                            "RequestDetails": json.dumps(request_details),
                            "RequestDescription": data.RequestDescription,
                            "RequestPriority": None,
                            "RequestStatus": "Pending",
                            "RequestAttachmentURL": data.RequestAttachmentURL,
                            "UpdatedTimeAndDate": None,
                            "RequestedBy": self.token_info["Id"],
                            "TenantUUID": tenantUUID,
                        },
                    )

                current_date += timedelta(days=1)

        self.db.commit()
        return JSONResponse(
            status_code=200, content={"message": "Request updated successfully"}
        )

    def update_other_request(
        self, data: UpdateRequestSchema, id, existing_request, request_table
    ):
        (
            request_type,
            request_details,
            request_description,
            request_priority,
            request_attachment_url,
        ) = self.prepare_update_data(data, existing_request)
        print(request_type, request_details, request_description,)
        fields_updated = []
        fields_values_updated = {}
        print("Existing request:----:", existing_request)
        existing_request = existing_request[0]
        # Check which fields are being updated
        if request_type == "ProfileChange" and isinstance(request_details, BaseModel):
            request_details = request_details.dict()

        if request_type != existing_request.get("RequestType"):
            fields_updated.append("RequestType")
            fields_values_updated["RequestType"] = {
                "before": existing_request.get("RequestType"),
                "after": request_type,
            }

        existing_details = existing_request.get("RequestDetails", {})
        if request_details != existing_details:
            fields_updated.append("RequestDetails")
            fields_values_updated["RequestDetails"] = {
                "before": existing_details,
                "after": request_details,
            }

        if request_description != existing_request.get("RequestDescription"):
            fields_updated.append("RequestDescription")
            fields_values_updated["RequestDescription"] = {
                "before": existing_request.get("RequestDescription"),
                "after": request_description,
            }

        if request_priority != existing_request.get("RequestPriority"):
            fields_updated.append("RequestPriority")
            fields_values_updated["RequestPriority"] = {
                "before": existing_request.get("RequestPriority"),
                "after": request_priority,
            }

        update_query = text(
            f"""
            UPDATE {request_table}
            SET "RequestType" = :RequestType, "RequestDetails" = :RequestDetails,
                "RequestDescription" = :RequestDescription, "RequestPriority" = :RequestPriority,
                "FieldsUpdated" = :FieldsUpdated, "FieldsValuesUpdated" = :FieldsValuesUpdated,
                "RequestAttachmentURL" = :RequestAttachmentURL, "UpdatedTimeAndDate" = CURRENT_TIMESTAMP
            WHERE "ID" = :ID
            """
        )

        self.db.execute(
            update_query,
            {
                "ID": id,
                "RequestType": request_type,
                "RequestDetails": json.dumps(request_details),
                "RequestDescription": request_description,
                "RequestPriority": request_priority,
                "FieldsUpdated": json.dumps(fields_updated),
                "RequestAttachmentURL": request_attachment_url,
                "FieldsValuesUpdated": json.dumps(
                    fields_values_updated, default=self.json_serial
                ),
            },
        )

        self.db.commit()
        return JSONResponse(
            status_code=200, content={"message": "Request updated successfully"}
        )

    def prepare_update_data(self, data: UpdateRequestSchema, existing_request):
        existing_request_item = existing_request[0]
        print("here2", existing_request_item)
        existing_details = existing_request_item.get("RequestDetails", "{}")
        print(existing_details)
        if data.RequestType == "HR":
            # Prepare data for HR request type
            return (
                "HR",
                {"RequestType": data.Type or existing_details.get("RequestType")},
                data.RequestDescription or existing_request_item.get("RequestDescription"),
                data.RequestPriority or existing_request_item.get("RequestPriority"),
                data.RequestAttachmentURL or existing_request_item.get("RequestAttachmentURL"),
            )
        elif data.RequestType == "Access":
            # Prepare data for Access request type
            return (
                "Access",
                {"Access": data.Type or existing_details.get("Access")},
                data.RequestDescription or existing_request_item.get("RequestDescription"),
                data.RequestPriority or existing_request_item.get("RequestPriority"),
                None,
            )
        elif data.RequestType == "ProfileChange":
            # Prepare data for ProfileChange request type
            return (
                "ProfileChange",
                existing_details,
                data.RequestDescription or existing_request_item.get("RequestDescription"),
                data.RequestPriority or existing_request_item.get("RequestPriority"),
                data.RequestAttachmentURL or existing_request_item.get("RequestAttachmentURL"),
            )
        elif data.RequestType == "TimeOff":
            # Prepare data for TimeOff request type
            return (
                "TimeOff",
                existing_details,
                data.RequestDescription or existing_request_item.get("RequestDescription"),
                data.RequestPriority or existing_request_item.get("RequestPriority"),
                data.RequestAttachmentURL or existing_request_item.get("RequestAttachmentURL"),
            )

        else:
            # Raise an error for unsupported request types
            raise ValueError("Invalid RequestType")

    async def delete_request(self, data: DeleteRequest):
        GetUser(self.db, data.Company_Portal_Url).verify_user(self.token_info)
        try:
            user = self.get_tenant_info(data.Company_Portal_Url)
            company_schema_name = user.SchemaName
            company_shortname = user.ShortName

            request_table = f"{company_schema_name}.tb_{
                company_shortname}_requests"
            request_ids = data.Request_Ids

            delete_query = text(
                f"""
                DELETE FROM {request_table}
                WHERE "ID" IN :Request_Ids
            """
            )
            self.revert_if_approved(data)
            self.db.execute(
                delete_query,
                {"Request_Ids": tuple(request_ids)},
            )

            self.db.commit()
            return JSONResponse(
                status_code=200,
                content={"message": "Selected requests deleted successfully"},
            )
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e
    
    def revert_if_approved(self, data: DeleteRequest):
        user = self.get_tenant_info(data.Company_Portal_Url)
        company_schema_name = user.SchemaName
        company_shortname = user.ShortName
        request_table = f"{company_schema_name}.tb_{company_shortname}_requests"
        timesheet_table = f"{company_schema_name}.tb_{company_shortname}_timesheet"
        
        result = self.get_existing_request(request_table, request_ids = data.Request_Ids)
        for request in result:
            if request["RequestType"] == 'TimeOff' and request["RequestStatus"] == "Approved":
                startDate = datetime.fromisoformat(request["RequestDetails"]["StartDate"])
                endDate = datetime.fromisoformat(request["RequestDetails"]["EndDate"])
                uuid = request["UserUUID"]
                task = "Time Off"
                dates_in_range = [(startDate + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((endDate - startDate).days + 1)]                
                query = text(f'''SELECT "ID" from {timesheet_table} WHERE DATE("Date") IN :date AND "ProjectBucket" = :task AND "UserUUID" = :uuid ''')
                result = self.db.execute(query, {
                    "date": tuple(dates_in_range), 
                    "task": task, 
                    "uuid": uuid
                })
                ids = [row[0] for row in result.fetchall()]
                print("\n idd",ids)
                CreateTimeSheetManager(self.db, self.token_info, data.Company_Portal_Url)._delete_timesheets(timesheet_table, ids )
    
    def handleApprovedTimeSheet(
        self,
        company_schema_name: str,
        company_shortname: str,
        request_data: Dict[str, Any]
    ):
        try:
            request_details = request_data.get("RequestDetails", "{}")
            Attachment = request_data.get("RequestAttachmentURL", "")
            TimeSheet = request_details.get("Time", [])
            UserUUID = request_data.get("UserUUID")
            print("\n TimeSheet", TimeSheet)
            print("\n UserUUID", UserUUID)
            print("\n Attachment", Attachment)
            print("\n RequestData", request_details)
            sowdata = SOWManager(self.db, self.token_info, self.Company_Portal_Url)
            User = GetUser(self.db, self.Company_Portal_Url)
            user = User.get_userdetails_by_uuid(UserUUID)
            print("\n User", user["SOW"][0])
            TimeEntry = [{
                "StartDate": entry.get("StartDate"),
                "EndDate": entry.get("EndDate"),
                "HoursWorked": entry.get("Hours")
            } for entry in TimeSheet]
            print(TimeEntry[0]["StartDate"])
            if TimeEntry and TimeEntry[0]["StartDate"]:
                month = datetime.fromisoformat(TimeEntry[0]["StartDate"]).month
            else:
                month = datetime.now().month 
            Timeshet = {
                "Client_Name": request_details.get("Client"),
                "Project_Name": request_details.get("Project"),
                "SOW_Name": str(sowdata._get_sow(projectUUID= request_details.get("Project"))[0]['SOWUUID']),
                "Project_Task": request_details.get("Task"),
                "time": TimeEntry
            }
            user_manager_details = User.get_userdetails_by_uuid(user["User_manager"])
            TimesheetData = {
                "Company_Portal_Url": self.Company_Portal_Url,
                "User_Manager": f"{user_manager_details['FirstName']} {user_manager_details['LastName']}",
                "Month": month,
                "time_sheet_attachment_key": Attachment,
                "Timesheet": [Timeshet],
                "IPAddress": "",
                "Latitude": "",
                "Longitude": "",
                "Notes": "",
                "uuid": UserUUID
            }
            print("\n TimesheetData", TimesheetData)
            CreateTimeSheetManager(self.db, self.token_info, self.Company_Portal_Url).create_time_sheet(
                TimesheetData, self.request)
        except json.JSONDecodeError:
            return error.error("Invalid RequestDetails format", 400, "Invalid RequestDetails format")
        except Exception as e:
            self.db.rollback()
            raise e
            
    def handleApprovedTimeOff(
        self,
        company_schema_name: str,
        company_shortname: str,
        request_data: Dict[str, Any]
    ):
        try:
            request_details = request_data.get("RequestDetails", "{}")
            Attachment = request_data.get("RequestAttachmentURL", "")
            StartDate = request_details.get("StartDate","")          
            EndDate = request_details.get("EndDate")  
            Hours = int(request_details.get("Hours"))
            UserUUID =request_data.get("UserUUID")
            TimeEntry = {
                "StartDate": StartDate,
                "EndDate": EndDate,
                "HoursWorked": Hours
            }
            Timeshet = {
                "Client_Name": company_shortname,
                "Project_Name": "Internal",
                "SOW_Name": "Internal",
                "Project_Task": "Time Off",
                "time": [TimeEntry]
            }
            timesheetData ={
                "Company_Portal_Url": self.Company_Portal_Url,
                "User_Manager": "",
                "Month": datetime.fromisoformat(StartDate).month,
                "time_sheet_attachment_key": Attachment,
                "Timesheet": [Timeshet],
                "IPAddress": "",
                "Latitude": "",
                "Longitude": "",
                "Notes": "",
                "uuid": UserUUID
            }
            CreateTimeSheetManager(self.db, self.token_info, self.Company_Portal_Url).create_time_sheet(timesheetData, self.request)
        except json.JSONDecodeError:
            return error.error("Invalid RequestDetails format", 400, "Invalid RequestDetails format")
        except Exception as e:
            self.db.rollback()
            raise e

    def handle_profile_change(
        self,
        company_schema_name: str,
        company_shortname: str,
        request_data: Dict[str, Any],
    ) -> None:

        try:
            # Extract the field to change
            request_details = request_data.get("RequestDetails", "{}")
            Attachment = request_data.get("RequestAttachmentURL", "")
            Detail_to_change = request_details.get("RequestDetailType", "")
            Detail_type_to_update = request_details.get("ChangeType", "")
            field_to_update = request_details.get("UpdateField", "")
            # Extract new value, handling different possible formats
            new_value = request_details.get("UpdateValue", "")
            # Clean up the new value by removing common prefixes
            if not new_value or not Detail_to_change:
                raise ValueError("Missing required field change information")

            bgv_table = f"{company_schema_name}.tb_{company_shortname}_bgv_info"
            bgv_report_table = f"{company_schema_name}.tb_{company_shortname}_bgv_report"
            bgv_result_table = f"{company_schema_name}.tb_{company_shortname}_bgv_result"
            user_table = f"{company_schema_name}.tb_{company_shortname}_user_info"

            if Detail_to_change == "IdentityDetails":
                if Detail_type_to_update == "PAN_Number":
                    attachmentType = "PAN_Image"
                elif Detail_type_to_update == "Aadhar_Number":
                    attachmentType = "Aadhar_Image"
                elif Detail_type_to_update == "Passport_FieldNumber" or "Passport_Number":
                    attachmentType = "Passport_Image"
                new_value = encrypt_data(new_value)
                if Detail_type_to_update == "UAN_Number":
                    # Only update the UAN_Number without an attachment
                    query = text(f'UPDATE {bgv_table} SET "{Detail_type_to_update}" = :ChangeValue WHERE "UserUUID" = :UserUUID')
                    params = {"ChangeValue": new_value,
                              "UserUUID": request_data.get("UserUUID")}
                else:
                    # Update both the field and the attachment
                    query = text(f'UPDATE {bgv_table} SET "{Detail_type_to_update}" = :ChangeValue, "{
                                 attachmentType}" = :Attachment WHERE "UserUUID" = :UserUUID')
                    params = {"ChangeValue": new_value, "UserUUID": request_data.get(
                        "UserUUID"), "Attachment": Attachment}

                
                try:
                    bgv_manager = UserBGVManager(db=self.db, Company_Portal_Url=self.Company_Portal_Url, logger=logger)
                    change_type = request_data["RequestDetails"]["ChangeType"]  # e.g., "Passport_FieldNumber"
                    update_value = request_data["RequestDetails"]["UpdateValue"]
                    verification_input = BritsUserBGVUpdateSchema(**{
                        change_type: update_value
                    })
                    print("Verification input:", verification_input)
                    bgv_manager.update_verification_results(
                        verification_input, request_data.get("UserUUID")
                    )
                except Exception as e:
                    print(f"Error updating BGV results at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
                    return error.error(f"Error updating BGV results: {str(e)}", 500, "Internal Server Error")
                
                self.db.execute(query, params)
                # self.db.commit()

            elif Detail_to_change == "Educational_Details":
                # Retrieve existing Educational_Details JSON data
                query = text(f'SELECT "Educational_Details" FROM {
                             bgv_table} WHERE "UserUUID" = :UserUUID')
                result = self.db.execute(
                    query, {"UserUUID": request_data.get("UserUUID")}).mappings().one()
                educational_details = result.get(
                    "Educational_Details", {}).get("Educational_Details", [])

                # Locate the specific entry to update
                for entry in educational_details:
                    print("\n", entry)
                    if entry.get("EducationType") == Detail_type_to_update:
                        # Update the specified field in the matched entry
                        entry[field_to_update] = new_value
                        break
                else:
                    raise ValueError(f"No entry found for EducationType: {
                                     Detail_type_to_update}")

                updated_educational_details = json.dumps(
                    {"Educational_Details": educational_details})

                update_query = text(f'UPDATE {
                                    bgv_table} SET "Educational_Details" = :UpdatedDetails WHERE "UserUUID" = :UserUUID')
                # report_update = text(f'UPDATE {
                #                      bgv_report_table} SET "Educational_Details" = :UpdatedDetails WHERE "UserUUID" = :UserUUID')
                try:
                    self.db.execute(update_query, {
                                    "UpdatedDetails": updated_educational_details, "UserUUID": request_data.get("UserUUID")})
                    # self.db.execute(report_update, {
                    #                 "UpdatedDetails": updated_educational_details, "UserUUID": request_data.get("UserUUID")})
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    raise e

            elif Detail_to_change == "Employment_Details":
                query = text(f'SELECT "Employment_Details" FROM {
                             bgv_table} WHERE "UserUUID" = :UserUUID')
                result = self.db.execute(
                    query, {"UserUUID": request_data.get("UserUUID")}).mappings().one()
                employment_details = result.get(
                    "Employment_Details").get("Employment_Details")

                for entry in employment_details:
                    if entry.get("CompanyName") == Detail_type_to_update:
                        # Update the specified field in the matched entry
                        entry[field_to_update] = new_value
                        break
                else:
                    raise ValueError(f"No entry found for EmploymentType: {
                                     Detail_type_to_update}")

                updated_employment_details = json.dumps(
                    {"Employment_Details": employment_details})

                update_query = text(f'UPDATE {
                                    bgv_table} SET "Employment_Details" = :UpdatedDetails WHERE "UserUUID" = :UserUUID')
                # report_update_query = text(f'UPDATE {
                #                            bgv_report_table} SET "Employment_Details" = :UpdatedDetails WHERE "UserUUID" = :UserUUID')
                try:
                    self.db.execute(update_query, {
                                    "UpdatedDetails": updated_employment_details, "UserUUID": request_data.get("UserUUID")})
                    # self.db.execute(report_update_query, {
                    #                 "UpdatedDetails": updated_employment_details, "UserUUID": request_data.get("UserUUID")})
                    self.db.commit()
                except Exception as e:
                    self.db.rollback()
                    raise e
                    
            elif Detail_to_change in ["ResidentialDetails", "PersonalDetails"]:
                query = text(f'UPDATE {bgv_table} SET "{Detail_type_to_update}" = :ChangeValue WHERE "UserUUID" = :UserUUID')
                params = {"ChangeValue": new_value, "UserUUID": request_data.get("UserUUID")}
                if Detail_to_change == "PersonalDetails" and Detail_type_to_update in ["FirstName", "LastName", "MobileNumber"]:
                    if Detail_type_to_update == "MobileNumber": Detail_type_to_update = "PhoneNumber"
                    usquery = text(f'UPDATE {user_table} SET "{Detail_type_to_update}" = :ChangeValue WHERE "UserUUID" = :UserUUID')
                    self.db.execute(usquery, params)
                self.db.execute(query, params)
                self.db.commit()
                
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid RequestDetails format")
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to process profile change: {str(e)}")
    
    async def approve_request(
        self, company_portal_url: str, request_ids: List[int], Choice: str
    ):        
        GetUser(self.db, company_portal_url).verify_user(self.token_info)
        try:
            if self.token_info["role"] not in ["Admin", "Manager", "HR"]:
                return error.error("You do not have the permission to perform this action", 401, "Unauthorized")
            user = self.get_tenant_info(company_portal_url)
            company_schema_name = user.SchemaName
            company_shortname = user.ShortName
            user_table = f"{user.SchemaName}.tb_{user.ShortName}_user_info"
            admin_query = text(
                f"SELECT \"Email\", \"FirstName\", \"LastName\" FROM {user_table} WHERE \"UserUUID\" = :user_uuid"
            )
            admin_details = self.db.execute(admin_query, {"user_uuid": self.token_info["Id"]}).fetchone()
            admin_name = f"{admin_details.FirstName} {admin_details.LastName}" if admin_details else "System Admin"
            print(admin_name, "-------------admin_name---------------")

            request_table = f"{company_schema_name}.tb_{
                company_shortname}_requests"
                
            tenant_settings_manager = TenantSettingsManager(self.db, company_portal_url)
            # Fetch all existing requests
            existing_requests = self.get_existing_request(
                request_table, request_ids=request_ids
            )
            print("here", existing_requests)
            if not existing_requests:
                return error.error("No valid requests found", 404, "No valid requests found")
            print("here1")
            # Check if any request has already been approved/denied
            already_processed = [
                r for r in existing_requests if (r.get("RequestStatus") == "Approved" and Choice == "Approve") or (r.get("RequestStatus") == "Denied" and Choice == "Deny")
            ]
            if already_processed:
                processed_ids = [r["ID"] for r in already_processed]
                return error.error(f"Request(s) with ID(s) {processed_ids} have already been {
                        Choice.lower()}d", 400, "Request(s) already processed")
            print("here2")
            

            
            update_query = text(
                f"""
                UPDATE {request_table}
                SET "RequestStatus" = :Status,
                    "ApprovedBy" = CASE WHEN :Choice = 'Approve' THEN CAST(:UserID AS UUID) ELSE NULL END,
                    "DeniedBy" = CASE WHEN :Choice = 'Deny' THEN CAST(:UserID AS UUID) ELSE NULL END,
                    "UpdatedTimeAndDate" = CURRENT_TIMESTAMP,
                    "FieldsUpdated" = :FieldsUpdated,
                    "FieldsValuesUpdated" = :FieldsValuesUpdated
                WHERE "ID" = ANY(:IDs)
                """
            )

            new_status = "Approved" if Choice == "Approve" else "Denied"
            fields_updated = json.dumps(["RequestStatus"])

            for request in existing_requests:
                print("Request:", request)
                fields_values_updated = json.dumps(
                    {
                        "RequestStatus": {
                            "before": [
                                r.get("RequestStatus") for r in existing_requests
                            ],
                            "after": new_status,
                        }
                    }
                )

                self.db.execute(
                    update_query,
                    {
                        "IDs": request_ids,
                        "UserID": self.token_info["Id"],
                        "Choice": Choice,
                        "Status": new_status,
                        "FieldsUpdated": fields_updated,
                        "FieldsValuesUpdated": fields_values_updated,
                    },
                )
                if request.get("RequestType") == "ProfileChange" and Choice == "Approve":
                    self.handle_profile_change(
                        company_schema_name,
                        company_shortname,
                        request
                    )
                elif request.get("RequestType") == "TimeOff" and Choice == "Approve":
                    self.handleApprovedTimeOff(
                        company_schema_name,
                        company_shortname,
                        request
                    )
                elif request.get("RequestType") == "TimeSheet" and Choice == "Approve":
                    self.handleApprovedTimeSheet(
                        company_schema_name,
                        company_shortname,
                        request
                    )
                
                # notData = {
                #     "to_uuid": str(request.get("UserUUID")),
                #     "from_uuid": self.token_info["Id"],
                #     "type": "Request",
                #     "action": Choice,
                #     "date": request.get("CreationTimeAndDate").strftime("%m-%d-%y"),
                #     "retype": request.get("RequestType"),
                # }
                # self._notification(notData)
            print("-----------------Send mail notification started-----------------")
            if await tenant_settings_manager.is_request_notification_enabled():
                user_table = f"{user.SchemaName}.tb_{user.ShortName}_user_info"
                user_query = text(
                    f"SELECT \"Email\", \"FirstName\", \"LastName\" FROM {user_table} WHERE \"UserUUID\" = :user_uuid"
                )
                user_details = self.db.execute(user_query, {"user_uuid": request.get("UserUUID")}).fetchone()
                all_dates = sorted([r["CreationTimeAndDate"] for r in existing_requests])
                if len(all_dates) == 1:
                    date_str = all_dates[0].strftime("%B %d, %Y")
                else:
                    date_str = f"{all_dates[0].strftime('%B %d, %Y')} to {all_dates[-1].strftime('%B %d, %Y')}"
                subject = request.get("RequestType")
                send_mail(
                    user_details.Email,
                    user_details.FirstName,
                    user_details.LastName,
                    "Request Notification",
                    company_portal_url,
                    "Request",
                    Choice,
                    admin_name,
                    date_str,
                    subject
                )   
            self.db.commit()
                
            all_dates = sorted([r["CreationTimeAndDate"] for r in existing_requests])
            request_types = list({r["RequestType"] for r in existing_requests})

            if len(all_dates) == 1:
                date_str = all_dates[0].strftime("%m-%d-%y")
            else:
                date_str = f"{all_dates[0].strftime('%m-%d-%y')} to {all_dates[-1].strftime('%m-%d-%y')}"
                
            for request_type in request_types:  
                notData = {
                    "to_uuid": str(request.get("UserUUID")),
                    "from_uuid": self.token_info["Id"],
                    "type": "Request",
                    "action": Choice,
                    "date": date_str,
                    "retype": request_type,
                }
                self._notification(notData)
                   
            return JSONResponse(
                status_code=200,
                content={
                    "message": f"{len(request_ids)} request {Choice.lower()}d successfully"
                },
            )
        except HTTPException as http_exc:
            print(f"Http Exception Occured at line number {sys.exc_info()[-1].tb_lineno}: {str(http_exc)}")
            raise http_exc
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            logger.error(f"Database Error Approve/Deny Request at line number {sys.exc_info()[-1].tb_lineno}: {str(sql_exc)}")
            raise sql_exc
        except Exception as e:
            logger.error(f"General Error Approve/Deny Request at line number {sys.exc_info()[-1].tb_lineno}: {str(e)}")
            raise e
