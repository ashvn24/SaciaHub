from datetime import datetime
import json
from typing import Dict, List, Optional
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from Models.Classes.TimesheetManager import CreateTimeSheetManager
from Models.Classes.GetUser import GetUser
from Models.Classes.customerVerifier import CustomerUserVerifier
from Models.db import models
from Models.db.schemas import HolidayScheme
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)


class ManageHolidayPolicy:
    def __init__(self, db: Session, token_info: Dict[str, str], request: Request = None) -> None:
        self.db = db
        self.token_info = token_info
        self.role = token_info["role"]
        self.admin_roles = ["Admin", "Manager", "HR"]
        self.request = request
        self.user = CustomerUserVerifier(self.db)

    def _verify_admin(self) -> None:
        if self.role not in self.admin_roles:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You do not have the permission to perform this action",
            )

    def _get_policy_table(self, schema_name: str, short_name: str) -> str:
        return f"{schema_name}.tb_{short_name}_holidaypolicy"

    def _get_user_table(self, schema_name: str, short_name: str) -> str:
        return f"{schema_name}.tb_{short_name}_user_info"

    def get_tenant_info(self, company_portal_url: str) -> models.TenantInfo:
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user

    def get_tenant(self, company_portal_url: str):
        tenant = self.get_tenant_info(company_portal_url)
        tenant_table = f"{tenant.SchemaName}.tb_{tenant.ShortName}_tenant_info"
        select_query = text(
            f"""
            SELECT "TenantUUID" from {tenant_table}
            """
        )
        result = self.db.execute(select_query)
        return result.mappings().one()

    def get_holiday_policy_template(self, params: Optional[int] = None) -> List[Dict]:
        self._verify_admin()
        try:
            filter_condition = 'WHERE "ID" = :ID' if params else ""
            query_params = {"ID": params} if params else {}
            select_query = text(
                f"""SELECT * FROM db_saciahub_sch_master.sch_master_tb_holiday_template
                {filter_condition}
                """
            )
            result = self.db.execute(select_query, query_params)
            return result.mappings().all()
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_holiday_policy_template: {str(e)}")
            raise e

    async def create_policy(self, data: HolidayScheme) -> Dict:
        self._verify_admin()
        try:
            user = self.get_tenant_info(data.Company_portal_Url)
            policy_table = self._get_policy_table(user.SchemaName, user.ShortName)
            insert_query = text(
                f"""
            INSERT INTO {policy_table} ("Template_Name", "Template_Country", "Holiday_Details")
            VALUES (:Template_Name, :Template_Country, :Holiday_Details);
            """
            )

            holiday_details = [
                {
                    "Holiday_Date": holiday.Holiday_Date,
                    "Holiday_Name": holiday.Holiday_Name,
                    "Holiday_mandatory": holiday.Holiday_mandatory,
                }
                for holiday in data.Holiday_Details
            ]
            self.db.execute(
                insert_query,
                {
                    "Template_Name": data.Template_Name,
                    "Template_Country": data.Template_Country,
                    "Holiday_Details": json.dumps(holiday_details),
                },
            )
            self.db.commit()

            return JSONResponse(
                status_code=201, content={"message": "Policy created successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in create_holiday_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in create_holiday_policy: {str(e)}")
            raise e

    async def get_holiday_policy(
        self, company_portal_url: str, ID: Optional[int] = None, sortBy: Optional[str] = None, order: Optional[int] = 1
    ) -> List[Dict]:
        try:
            self._verify_admin()
            user = self.get_tenant_info(company_portal_url)
            policy_table = self._get_policy_table(user.SchemaName, user.ShortName)

            filter_condition = 'WHERE "ID" = :ID' if ID else ""
            query_params = {"ID": ID} if ID else {}

            sort_column_map = {
                "policyname": '"Template_Name"',
                "country": '"Template_Country"',
                "days": "jsonb_array_length(\"Holiday_Details\"::jsonb)",
                "status": '"HolidayAttachmentURL"'  # or change to actual "Status" field if exists
            }

            # Default sort
            order_dir = "ASC" if order == 1 else "DESC"
            order_clause = ""
            if sortBy:
                sort_key = sortBy.lower()
                if sort_key in sort_column_map:
                    order_clause = f"ORDER BY {sort_column_map[sort_key]} {order_dir}"
                else:
                    order_clause = 'ORDER BY "ID" ASC'
            else:
                order_clause = 'ORDER BY "ID" ASC'


            select_query = text(
                f"""SELECT * FROM {policy_table}
                {filter_condition}
                {order_clause}
                """
            )
            result = self.db.execute(select_query, query_params)
            policies = result.mappings().all()

            if not policies:
                return error.error("Holiday policy not found", 404, "Holiday Policy Not Found")
            return policies
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_holiday_policy: {str(e)}")
            raise e

    async def update_policy(self, data: HolidayScheme, ID: int) -> Dict:
        self._verify_admin()
        try:
            user = self.get_tenant_info(data.Company_portal_Url)
            policy_table = self._get_policy_table(user.SchemaName, user.ShortName)

            update_query = text(
                f"""
                UPDATE {policy_table}
                SET "Template_Country" = :Template_Country,
                    "Holiday_Details" = :Holiday_Details,
                    "Template_Name" = :Template_Name
                WHERE "ID" = :ID;
                """
            )

            holiday_details = [
                {
                    "Holiday_Date": holiday.Holiday_Date,
                    "Holiday_Name": holiday.Holiday_Name,
                    "Holiday_mandatory": holiday.Holiday_mandatory,
                }
                for holiday in data.Holiday_Details
            ]

            self.db.execute(
                update_query,
                {
                    "ID": ID,
                    "Template_Name": data.Template_Name,
                    "Template_Country": data.Template_Country,
                    "Holiday_Details": json.dumps(holiday_details),
                },
            )
            self.db.commit()

            return JSONResponse(
                status_code=200, content={"message": "Policy updated successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in update_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in update_policy: {str(e)}")
            raise e

    async def delete_policy(self, company_portal_url: str, ID: int) -> Dict:
        self._verify_admin()
        try:
            user = self.get_tenant_info(company_portal_url)
            policy_table = self._get_policy_table(user.SchemaName, user.ShortName)

            delete_query = text(
                f"""
                DELETE FROM {policy_table}
                WHERE "ID" = :ID
                """
            )
            result = self.db.execute(delete_query, {"ID": ID})
            self.db.commit()

            if result.rowcount == 0:
                raise error.error("Time-off policy not found", 404, "Time-Off Policy Not Found")

            logger.info(f"Time-off policy deleted successfully for ID: {ID}")
            return JSONResponse(
                status_code=200, content={"message": "Policy deleted successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in delete_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in delete_policy: {str(e)}")
            raise e

    async def assign_policy(
        self, company_portal_url: str, ID: int, policyID: int
    ) -> Dict:
        try:
            user = self.get_tenant_info(company_portal_url)
            userinfo = self._get_user_table(user.SchemaName, user.ShortName)

            update_query = text(
                f"""
                UPDATE {userinfo}
                SET "Holiday_Policy" = :Holiday_Policy
                WHERE "ID" = :ID;
                """
            )
            self.db.execute(update_query, {"Holiday_Policy": policyID, "ID": ID})
            self.db.commit()
            await self.populate_timesheet(company_portal_url, policyID, ID)
            return JSONResponse(
                status_code=200, content={"message": "Policy Assigned successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in update_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in update_policy: {str(e)}")
            raise e

    async def populate_timesheet(
        self, company_portal_url: str, policyID: int, ID: int
    ) -> None:
        try:
            policy = await self.get_holiday_policy(company_portal_url, ID=policyID)
            current_timezone = datetime.now().astimezone().tzinfo
            current_date = datetime.now().astimezone(current_timezone)
            print("here")
            timesheet_entries = []
            for row in policy:
                for holiday in row["Holiday_Details"]:
                    if len(holiday["Holiday_Date"].split()) < 2:
                        logger.warning(
                            f"Skipping incomplete date entry: {holiday['Holiday_Date']}"
                        )
                        continue
                    start_date = datetime.strptime(
                        holiday["Holiday_Date"], "%B %d"
                    ).replace(year=datetime.now().year, tzinfo=current_timezone)

                    if start_date > current_date:
                        timesheet_entries.append(
                            {
                                "StartDate": start_date,
                                "EndDate": start_date,
                                "HoursWorked": 9,
                            }
                        )

            client = company_portal_url.split(".")[0]
            if client.startswith("dev"):
                client = client[3:]  # Remove "dev" prefix
            data = {
                "Company_Portal_Url": company_portal_url,
                "User_Manager": "",
                "time_sheet_attachment_key": "",
                "Month": None,
                "Timesheet": [
                    {
                        "Client_Name": client,
                        "Project_Name": "Internal",
                        "SOW_Name": "Internal",
                        "Project_Task": "PHT",
                        "time": timesheet_entries,
                    }
                ],
                "Notes": "Holiday",
                "IPAddress": "",
                "Latitude": "",
                "Longitude": "",
                "uuid": GetUser(self.db, company_portal_url).get_user_uuids([ID])[0],
            }
            CreateTimeSheetManager(
                self.db, self.token_info, company_portal_url
            ).create_time_sheet(data, self.request)

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in policy: {str(e)}")
            raise e

    def _distribute_hours(
        self, start_date: datetime, end_date: datetime, hours_worked: float
    ) -> float:
        num_days = (end_date - start_date).days + 1
        return hours_worked / num_days

    def _handle_exception(self, exception: Exception) -> None:
        self.db.rollback()
        if isinstance(exception, HTTPException):
            raise exception
        logger.error(f"Error occurred: {str(exception)}")
        raise HTTPException(
            status_code=500, detail="An error occurred while processing the request."
        )

    def get_approved_timeoff(self, company_portal_url: str) -> JSONResponse:
        try:
            self._verify_admin()
            user = self.get_tenant_info(company_portal_url)
            users_table = f"{user.SchemaName}.tb_{user.ShortName}_user_info"
            timeoff_table = f"{user.SchemaName}.tb_{user.ShortName}_requests"
            select_query = text(
                f"""
                SELECT 
                    u."FirstName", 
                    u."LastName", 
                    u."JobTitle", 
                    u."UserUUID",
                    u."ProfilePictureURL",
                    t."RequestDetails"
                FROM {users_table} u
                JOIN {timeoff_table} t ON u."UserUUID" = t."UserUUID"
                WHERE t."RequestType" = 'TimeOff' 
                AND t."RequestStatus" = 'Approved'
                """
            )
            result = self.db.execute(select_query).mappings().all()
            data = [
                {
                    "FirstName": row["FirstName"],
                    "LastName": row["LastName"],
                    "UserUUID": str(row["UserUUID"]),
                    "JobTitle": row["JobTitle"],
                    "ProfilePicture": row["ProfilePictureURL"],
                    "StartDate": row["RequestDetails"]["StartDate"],
                    "EndDate": row["RequestDetails"]["EndDate"],
                }
                for row in result
            ]
            return JSONResponse(status_code=200, content=data)
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_approved_timeoff: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in get_approved_timeoff: {str(e)}")
            raise e

    async def getUserHoliday(self, company_portal_url: str) -> Optional[Dict]:
        try:
            user = self.get_tenant_info(company_portal_url)
            policy_table = self._get_policy_table(user.SchemaName, user.ShortName)
            user_table = self._get_user_table(user.SchemaName, user.ShortName)
            query = text(
                f"""
                SELECT p."Holiday_Details" 
                FROM {policy_table} p
                JOIN {user_table} u ON u."Holiday_Policy" = p."ID"
                WHERE u."UserUUID" = :user_uuid
            """
            )

            result = self.db.execute(
                query, {"user_uuid": self.token_info["Id"]}
            ).mappings().one_or_none()

            return result
        except Exception as e:
            logger.error(f"Unexpected error in holidayPolicy: {str(e)}")
            raise e
