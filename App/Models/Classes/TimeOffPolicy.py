import json
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
from App.Models.Classes.GetUser import GetUser
from Models.db import models
from Models.db.schemas import TimeOffPolicySchema
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()

logger = logging.getLogger(__name__)


class ManageTimeoffPolicy:
    def __init__(self, db: Session, token_info: Dict[str, str]) -> None:
        self.db = db
        self.token_info = token_info
        self.role = token_info["role"]
        self.admin_roles = ["Admin", "Manager", "HR"]

    def _get_timeoff_policy_table(self, schema_name: str, short_name: str) -> str:
        return f"{schema_name}.tb_{short_name}_timeoff_policy"

    def _get_user_table(self, schema_name: str, short_name: str) -> str:
        return f"{schema_name}.tb_{short_name}_user_info"

    def _verify_admin(self) -> None:
        if self.role not in self.admin_roles:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You do not have the permission to perform this action",
            )

    def get_tenant_info(self, company_portal_url: str) -> models.TenantInfo:
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Schema not found")
        return user

    def get_tenant(self, Company_portal_Url):
        tenant = self.get_tenant_info(Company_portal_Url)
        tenant_table = f"{tenant.SchemaName}.tb_{tenant.ShortName}_tenant_info"
        select_query = text(
            f"""
            SELECT "TenantUUID" from {tenant_table}
            """
        )
        result = self.db.execute(select_query)
        return result.mappings().one()

    def get_timeoff_policy_template(self, params: Optional[int] = None, sortBy: Optional[str] = None, order: Optional[int] = 1) -> List[Dict]:
        self._verify_admin()
        try:
            sort_column_map = {
                "policyname": '"Timeoff_Policy_Name"',
                "country": '"Timeoff_Country"',
                "timeofftype": 'jsonb_array_length("Timeoff_Details")',  # Or change to a specific key if needed
                "hours": '"Yearly_Total_Hours"',
                "status": '"Status"'
            }
            # ORDER direction
            order_dir = "ASC" if order == 1 else "DESC"

            # Determine WHERE clause
            filter_condition = 'WHERE "ID" = :ID' if params else ""
            query_params = {"ID": params} if params else {}

            # Determine ORDER BY clause
            if sortBy and sortBy.lower() in sort_column_map:
                order_clause = f'ORDER BY {sort_column_map[sortBy.lower()]} {order_dir}'
            else:
                order_clause = 'ORDER BY "ID" ASC'  # default fallback

            select_query = text(
                f"""SELECT * FROM db_saciahub_sch_master.sch_master_tb_timeoff_policy
                {order_clause}
                """
            )
            result = self.db.execute(select_query, query_params)
            return result.mappings().all()
        except SQLAlchemyError as e:
            logger.error(
                f"Database error in get_timeoff_policy_template: {str(e)}")
            raise e

    async def create_timeoff_policy(self, data: TimeOffPolicySchema) -> Dict:
        GetUser(self.db, data.Company_portal_Url).verify_user(self.token_info)
        self._verify_admin()
        try:
            user = self.get_tenant_info(data.Company_portal_Url)
            timeoffpolicy_table = self._get_timeoff_policy_table(
                user.SchemaName, user.ShortName
            )
            tenant_uuid = self.get_tenant(data.Company_portal_Url)

            print(tenant_uuid,"-----",self.get_tenant_info(data.Company_portal_Url))

            daily_hours = 8
            timeoff_types = data.TimeOff_Type

            monthly_working_hours = daily_hours * 22
            yearly_working_hours = monthly_working_hours * 12
            yearly_total_hours = yearly_working_hours

            paid_timeoff_days = 0
            paid_sick_days = 0
            unpaid_timeoff_days = 0
            paid_timeoff_hours = 0
            paid_sick_hours = 0
            unpaid_timeoff_hours = 0

            for timeoff in timeoff_types:
                timeoff_type = timeoff["type"]
                hours = timeoff["hours"]

                if timeoff_type == "PTO":
                    paid_timeoff_days = (hours / daily_hours) * 12
                    paid_timeoff_hours = (hours * 12)
                elif timeoff_type == "Sick":
                    paid_sick_days = (hours / daily_hours) * 12
                    paid_sick_hours = (hours * 12)
                elif timeoff_type == "UTO":
                    unpaid_timeoff_days = (hours / daily_hours) * 12
                    unpaid_timeoff_hours = (hours * 12)
                else:
                    raise HTTPException(status_code=400, detail="Invalid TimeOff_Type")

            paid_timeoff_days = int(paid_timeoff_days)
            paid_sick_days = int(paid_sick_days)
            unpaid_timeoff_days = int(unpaid_timeoff_days)
            paid_timeoff_hours = int(paid_timeoff_hours)
            unpaid_timeoff_hours = int(unpaid_timeoff_hours)
            paid_sick_hours = int(paid_sick_hours)
        


            timeoff_details = {
                "Timeoff_Type": ",".join([timeoff["type"] for timeoff in timeoff_types]),
                "Paid_timeoff_hours": paid_timeoff_hours,
                "Paid_timeoff_days": paid_timeoff_days,
                "Unpaid_timeoff_hours": unpaid_timeoff_hours,
                "Unpaid_timeoff_days": unpaid_timeoff_days,
                "Paid_sick_hours": paid_sick_hours,
                "Paid_sick_days": paid_sick_days,
            }

            insert_query = text(
                f"""
                INSERT INTO {timeoffpolicy_table} ("Timeoff_Policy_Name", "Timeoff_Country", "Daily_Working_Hours",
                "Monthly_Working_Hours", "Yearly_Working_Hours", "Yearly_Total_Hours", "Timeoff_Details", "TenantUUID")
                VALUES (:Timeoff_Policy_Name, :Timeoff_Country, :Daily_Working_Hours, :Monthly_Working_Hours,
                :Yearly_Working_Hours, :Yearly_Total_Hours, :Timeoff_Details, :tenant_uuid);
                """
            )

            # timeoff_details = {
            #     "Paid_timeoff_hours": data.Paid_timeoff_hours,
            #     "Paid_timeoff_days": data.Paid_timeoff_days,
            #     "Unpaid_timeoff_hours": data.Unpaid_timeoff_hours,
            #     "Unpaid_timeoff_days": data.Unpaid_timeoff_days,
            #     "Paid_sick_hours": data.Paid_sick_hours,
            #     "Paid_sick_days": data.Paid_sick_days,
            # }

            self.db.execute(
            insert_query,
            {
                "Timeoff_Policy_Name": data.Timeoff_Policy_Name,
                "Timeoff_Country": data.Timeoff_Country,
                "Daily_Working_Hours": daily_hours,
                "Monthly_Working_Hours": monthly_working_hours,
                "Yearly_Working_Hours": yearly_working_hours,
                "Yearly_Total_Hours": yearly_total_hours,
                "Timeoff_Details": json.dumps(timeoff_details),
                "tenant_uuid": tenant_uuid["TenantUUID"]
            },
        )
            self.db.commit()
            logger.info(
                f"Time-off policy created successfully for tenant: {
                    user.TenantUUID}"
            )
            return JSONResponse(
                status_code=201,
                content={"message": "Policy created successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in create_timeoff_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error in create_timeoff_policy: {str(e)}")
            raise e

    async def get_timeoff_policy(self, Company_portal_Url: str, ID: Optional[int] = None) -> List[Dict]:
        try:
            GetUser(self.db, Company_portal_Url).verify_user(self.token_info)
            user = self.get_tenant_info(Company_portal_Url)
            timeoffpolicy_table = self._get_timeoff_policy_table(
                user.SchemaName, user.ShortName
            )
            filter_condition = 'WHERE "ID" = :ID' if ID else ""
            query_params = {"ID": ID} if ID else {}

            select_query = text(
                f"""SELECT * FROM {timeoffpolicy_table}
                {filter_condition}
                """
            )
            result = self.db.execute(select_query, query_params)
            policies = result.mappings().all()
            data = []
            for policy in policies:
                timeoff_details = policy["Timeoff_Details"]

                # Split timeoff types
                timeoff_types_raw = timeoff_details.get("Timeoff_Type", "")
                timeoff_types = timeoff_types_raw.split(",") if timeoff_types_raw else []

                # Construct desired time_off_types list
                time_off_type_list = []
                for t_type in timeoff_types:
                    t_type = t_type.strip()
                    if t_type == 'PTO':
                        hours = int(timeoff_details.get("Paid_timeoff_hours")/12) if timeoff_details.get("Paid_timeoff_hours") else 0
                    elif t_type == 'Sick':
                        hours = int(timeoff_details.get("Paid_sick_hours")/12) if timeoff_details.get("Paid_sick_hours") else 0
                    elif t_type == 'UTO':
                        hours = int(timeoff_details.get("Unpaid_timeoff_hours")/12) if timeoff_details.get("Unpaid_timeoff_hours") else 0
                    time_off_type_list.append({
                        "type": t_type,
                        "hours": hours
                    })

                # Filter Hours excluding timeoff type + *_hours
                hours = {
                    k: v for k, v in timeoff_details.items()
                    if k not in ["Timeoff_Type"] and not k.endswith("_hours")
                }

                data.append({
                    "id": policy["ID"],
                    "policy_name": policy["Timeoff_Policy_Name"],
                    "country": policy["Timeoff_Country"],
                    "time_off_types": time_off_type_list,
                    # "Hours": hours,
                    "Status": policy["Status"]
                })

            if not policies:
                return error.error("Time-off policy not found", 404, "Time-off Policy")
            return data
        
        except SQLAlchemyError as e:
            logger.error(f"Database error in get_timeoff_policy: {str(e)}")
            raise e
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Unexpected error in get_timeoff_policy: {str(e)}")
            print("Unexpected error in get_timeoff_policy: ",str(e))
            raise e

    async def update_timeoff_policy(self, data: TimeOffPolicySchema, ID: int) -> Dict:
        GetUser(self.db, data.Company_portal_Url).verify_user(self.token_info)
        self._verify_admin()

        try:
            user = self.get_tenant_info(data.Company_portal_Url)
            timeoffpolicy_table = self._get_timeoff_policy_table(
                user.SchemaName, user.ShortName
            )

            daily_hours = 8
            timeoff_types = data.TimeOff_Type

            monthly_working_hours = daily_hours * 22
            yearly_working_hours = monthly_working_hours * 12
            yearly_total_hours = yearly_working_hours

            # Initialize counters
            paid_timeoff_days = 0
            paid_sick_days = 0
            unpaid_timeoff_days = 0
            paid_timeoff_hours = 0
            paid_sick_hours = 0
            unpaid_timeoff_hours = 0

            for timeoff in timeoff_types:
                timeoff_type = timeoff["type"]
                hours = timeoff["hours"]

                if timeoff_type == "PTO":
                    paid_timeoff_days = (hours / daily_hours) * 12
                    paid_timeoff_hours = hours * 12
                elif timeoff_type == "Sick":
                    paid_sick_days = (hours / daily_hours) * 12
                    paid_sick_hours = hours * 12
                elif timeoff_type == "UTO":
                    unpaid_timeoff_days = (hours / daily_hours) * 12
                    unpaid_timeoff_hours = hours * 12
                else:
                    return error.error("Invalid TimeOff_Type", 400, "TimeOff_Type")

            # Convert to integers
            paid_timeoff_days = int(paid_timeoff_days)
            paid_sick_days = int(paid_sick_days)
            unpaid_timeoff_days = int(unpaid_timeoff_days)
            paid_timeoff_hours = int(paid_timeoff_hours)
            unpaid_timeoff_hours = int(unpaid_timeoff_hours)
            paid_sick_hours = int(paid_sick_hours)

            timeoff_details = {
                "Timeoff_Type": ",".join([timeoff["type"] for timeoff in timeoff_types]),
                "Paid_timeoff_hours": paid_timeoff_hours,
                "Paid_timeoff_days": paid_timeoff_days,
                "Unpaid_timeoff_hours": unpaid_timeoff_hours,
                "Unpaid_timeoff_days": unpaid_timeoff_days,
                "Paid_sick_hours": paid_sick_hours,
                "Paid_sick_days": paid_sick_days,
            }

            update_query = text(
                f"""
                UPDATE {timeoffpolicy_table}
                SET "Timeoff_Policy_Name" = :Timeoff_Policy_Name,
                    "Timeoff_Country" = :Timeoff_Country,
                    "Daily_Working_Hours" = :Daily_Working_Hours,
                    "Monthly_Working_Hours" = :Monthly_Working_Hours,
                    "Yearly_Working_Hours" = :Yearly_Working_Hours,
                    "Yearly_Total_Hours" = :Yearly_Total_Hours,
                    "Timeoff_Details" = :Timeoff_Details,
                    "TenantUUID" = :TenantUUID
                WHERE "ID" = :ID;
                """
            )

            result = self.db.execute(
                update_query,
                {
                    "Timeoff_Policy_Name": data.Timeoff_Policy_Name,
                    "Timeoff_Country": data.Timeoff_Country,
                    "Daily_Working_Hours": daily_hours,
                    "Monthly_Working_Hours": monthly_working_hours,
                    "Yearly_Working_Hours": yearly_working_hours,
                    "Yearly_Total_Hours": yearly_total_hours,
                    "Timeoff_Details": json.dumps(timeoff_details),
                    "TenantUUID": user.TenantUUID,
                    "ID": ID,
                },
            )
            self.db.commit()

            if result.rowcount == 0:
                return error.error("Time-off policy not found", 404, "Time-off Policy")

            logger.info(f"Time-off policy updated successfully for ID: {ID}")
            return JSONResponse(
                status_code=200,
                content={"message": "Policy updated successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in update_timeoff_policy: {str(e)}")
            raise HTTPException(status_code=500, detail="Database error occurred")
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Unexpected error in update_timeoff_policy: {str(e)}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


    async def delete_policy(self, Company_portal_Url: str, ID: int) -> Dict:
        GetUser(self.db, Company_portal_Url).verify_user(self.token_info)
        self._verify_admin()
        try:
            user = self.get_tenant_info(Company_portal_Url)
            timeoffpolicy_table = self._get_timeoff_policy_table(
                user.SchemaName, user.ShortName
            )

            delete_query = text(
                f"""
                DELETE FROM {timeoffpolicy_table}
                WHERE "ID" = :ID
                """
            )
            result = self.db.execute(delete_query, {"ID": ID})
            self.db.commit()

            if result.rowcount == 0:
                return error.error("Time-off policy not found", 404, "Time-off Policy")

            logger.info(f"Time-off policy deleted successfully for ID: {ID}")
            return JSONResponse(
                status_code=200,
                content={"message": "Policy deleted successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in delete_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in delete_policy: {str(e)}")
            raise e

    async def assign_policy(self, Company_portal_Url: str, ID: int, policyID: int):
        GetUser(self.db, Company_portal_Url).verify_user(self.token_info)
        try:
            user = self.get_tenant_info(Company_portal_Url)
            userinfo = self._get_user_table(user.SchemaName, user.ShortName)

            update_query = text(
                f"""
                UPDATE {userinfo}
                SET "Timeoff_Policy" = :Timeoff_Policy
                WHERE "ID" = :ID;
                """
            )
            self.db.execute(
                update_query, {"Timeoff_Policy": policyID, "ID": ID})
            self.db.commit()
            return JSONResponse(
                status_code=200,
                content={"message": "Policy Assigned successfully"}
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error in update_timeoff_policy: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"Unexpected error in update_timeoff_policy: {str(e)}")
            raise e
