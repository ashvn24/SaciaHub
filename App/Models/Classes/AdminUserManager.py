import json
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import uuid
import logging

from Models.Classes.GetUser import GetUser
from Models.Classes.folderManager import FolderManager
from Models.db import models
from Models.db.schemas import BritsUserSchema, FolderSchema
from Models.utils.send_mail import send_mail_func
from Models.Classes.token_authentication import create_access_token, generate_random_password, get_password_hash
from Models.utils.error_handler import ErrorHandler

logger = logging.getLogger(__name__)
error = ErrorHandler()


class UserManager:
    def __init__(self, db: Session):
        self._db = db
        self._customer_info = None
        self.pswd = None

    @property
    def db(self):
        return self._db

    @property
    def customer_info(self):
        if self._customer_info is None:
            raise ValueError(
                "Customer info not set. Call set_customer_info() first.")
        return self._customer_info

    @staticmethod
    def get_user_table_name(schema_name: str, shortname: str):
        return f"{schema_name}.tb_{shortname}_user_info"

    @staticmethod
    def generate_portal_url(shortname: str):
        return f"{shortname}.saciahub.com"

    def set_customer_info(self, portal_url: str):
        customer = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == portal_url)
            .first()
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        self.tenant = customer
        self._customer_info = {
            'schema_name': customer.SchemaName,
            'shortname': customer.ShortName
        }

    @staticmethod
    def validate_admin_role(token_info: dict):
        if token_info["role"] != "Admin":
            return error.error("You do not have the permission to perform this action", 401, "Admin Role")

    @staticmethod
    def validate_admin_or_manager_role(token_info: dict):
        if token_info["role"] not in ["Admin", "Manager", "HR"]:
            return error.error("You do not have the permission to perform this action", 401, "Admin or Manager Role")

    async def update_user_status(self, user_id: str, company_portal_url: str, token_info: dict):
        self.validate_admin_role(token_info)
        GetUser(self.db, company_portal_url).verify_user(token_info)
        try:
            self.set_customer_info(company_portal_url)
            user_table_name = self.get_user_table_name(
                self.customer_info['schema_name'],
                self.customer_info['shortname']
            )

            existing_user = self._get_user_by_id(user_table_name, user_id)
            if not existing_user:
                return error.error("User not found", 404, "User Not Found")

            new_status = "Inactive" if existing_user.Status == "Active" else "Active"
            self._update_user_status(user_table_name, user_id, new_status)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "User status updated successfully"}
            )
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise e
    
    async def register_user(self, data: BritsUserSchema, token_info: dict):
        self.token_info = token_info
        self.Company_Portal_Url = data.Company_Portal_Url
        self.validate_admin_or_manager_role(token_info)
        GetUser(self.db, data.Company_Portal_Url).verify_user(token_info)
        try:
            self.set_customer_info(data.Company_Portal_Url)
            user_table_name = self.get_user_table_name(
                self.customer_info['schema_name'],
                self.customer_info['shortname']
            )
            print("Customer Info:", self.customer_info)
            print("User Table Name:", user_table_name)

            if self._user_exists(user_table_name, data.User_Email):
                return error.error("User already exists or Email is already in use", 400, "User Already Exists")

            new_user_id = self._insert_new_user(user_table_name, data)
            print("New User ID:", new_user_id)
            self._send_welcome_email(data)

            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={"message": "User created successfully",
                         "user_id": new_user_id}
            )
        except HTTPException as http_exc:
            raise http_exc
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            raise sql_exc
        except Exception as e:
            raise e

    def _get_user_by_id(self, table_name: str, user_id: str):
        query = text(f'SELECT * FROM {table_name} WHERE "ID" = :ID')
        return self.db.execute(query, {"ID": user_id}).fetchone()

    def _update_user_status(self, table_name: str, user_id: str, new_status: str):
        update_query = text(
            f'UPDATE {table_name} SET "Status" = :Status WHERE "ID" = :ID'
        )
        self.db.execute(update_query, {"Status": new_status, "ID": user_id})
        self.db.commit()

    def _user_exists(self, table_name: str, email: str):
        email_query = text(
            f'SELECT * FROM {table_name} WHERE "Email" = :Email')
        return (
            self.db.execute(
                email_query, {"Email": email}).fetchone() is not None
        )

    def _insert_new_user(self, table_name: str, data: BritsUserSchema):
        try:
            insert_query = text(
                f"""
                INSERT INTO {table_name} ("UserUUID", "User_Id", "FirstName", "LastName", "Email", "Password", "Role", "Module", "JobTitle", "User_manager",
                "UserTeam", "PasswordLastSet", "TenantUUID", "HR_Manager")
                VALUES (:UserUUID, :User_Id, :FirstName, :LastName, :Email, :Password, :Role, :Module, :JobTitle, :User_manager, :UserTeam, :PasswordLastSet, :tenant, :HR_Manager)
                RETURNING "ID"
                """
            )
            print("Insert Query passed")
            
            # Handle Manager UUID
            managerid = None
            if data.Manager:
                manager_uuids = GetUser(self.db, self.Company_Portal_Url).get_user_uuids([str(data.Manager)])
                managerid = manager_uuids[0] if manager_uuids else None
                
            # Handle HR Manager UUID    
            hr_managerid = None
            if data.HR_Manager:
                hr_manager_uuids = GetUser(self.db, self.Company_Portal_Url).get_user_uuids([str(data.HR_Manager)])
                hr_managerid = hr_manager_uuids[0] if hr_manager_uuids else None
                
            self.pswd = generate_random_password()
            print(f"Generated password: {self.pswd}")

            # Prepare user data with proper null handling
            user_data = {
                "UserUUID": uuid.uuid4(),
                "User_Id": models.generate_user_id(),
                "FirstName": data.FirstName,
                "LastName": data.LastName,
                "Email": data.User_Email.lower(),
                "Password": get_password_hash(self.pswd),
                "Role": data.User_role or "user",
                "Module": json.dumps(data.module),
                "User_manager": managerid,
                "JobTitle": data.Job_Role,
                "UserTeam": json.dumps(data.Team) if data.Team else None,
                "PasswordLastSet": datetime.now(),
                "tenant": self.tenant.TenantUUID,
                "HR_Manager": hr_managerid
            }

            print("User data before insert:", user_data)
            
            result = self.db.execute(insert_query, user_data)
            self.db.commit()
            
            # Create user folder
            folder_data = FolderSchema(
                FolderName=data.FirstName,
                ParentFolderID=None,
                EntityType="User"
            )
            
            return result.fetchone()[0]
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            print(f"Insertion Error: {e}")
            print(f"User Data: {user_data}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"An unexpected error occurred: {str(e)}")
            raise e
    def _send_welcome_email(self, data: BritsUserSchema):
        print("Sending Email")
        try:
            send_mail_func(
            data.User_Email.lower(),
            FirstName=data.FirstName,
            password=create_access_token({"user":data.User_Email}, expires_delta=timedelta(days=1)),
            subject="welcome",
            company_portal_url=data.Company_Portal_Url
        )
        except Exception as e:
            print(f"Error sending email: {e}")
            raise e

    def update_user(self, user_id: str, data: BritsUserSchema, token_info: dict):
        self.validate_admin_or_manager_role(token_info)
        # Set Company_Portal_Url as class attribute
        self.Company_Portal_Url = data.Company_Portal_Url
        GetUser(self.db, data.Company_Portal_Url).verify_user(token_info)
        try:
            self.set_customer_info(data.Company_Portal_Url)
            user_table_name = self.get_user_table_name(
                self.customer_info['schema_name'],
                self.customer_info['shortname']
            )

            existing_user = self._get_user_by_id(user_table_name, user_id)
            if not existing_user:
                return error.error("User not found", 404, "User Not Found")
            
            print("User ID:", user_id)
            print("Module:", data.module)
            
            # Check for duplicate email
            email_check_query = text(f"""
                SELECT 1 FROM {user_table_name}
                WHERE LOWER("Email") = :email AND "ID" != :user_id
                LIMIT 1
            """)
            email_exists = self.db.execute(email_check_query, {
                "email": data.User_Email.lower(),
                "user_id": user_id
            }).fetchone()

            if email_exists:
                return error.error("Email already exists for another user.", 400, "Email Already Exists")

            self._update_user(user_table_name, user_id, data)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "User updated successfully"}
            )
        except HTTPException as http_exc:
            raise http_exc
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            raise sql_exc
        except Exception as e:
            raise e

    def _update_user(self, table_name: str, user_id: str, data: BritsUserSchema):
        update_query = text(
            f"""
            UPDATE {table_name}
            SET 
                "FirstName" = :FirstName,
                "LastName" = :LastName,
                "Email" = :Email,
                "User_manager" = :User_manager,
                "UserTeam" = :UserTeam,
                "Module" = :Module,
                "JobTitle" = :JobTitle,
                "Role" = :Role,
                "HR_Manager" = :HR_Manager
            WHERE "ID" = :ID
            """
        )
        
        # Handle Manager UUID
        managerid = None
        if data.Manager:
            manager_uuids = GetUser(self.db, self.Company_Portal_Url).get_user_uuids([str(data.Manager)])
            managerid = manager_uuids[0] if manager_uuids else None
            
        # Handle HR Manager UUID    
        hr_managerid = None
        if data.HR_Manager:
            hr_manager_uuids = GetUser(self.db, self.Company_Portal_Url).get_user_uuids([str(data.HR_Manager)])
            hr_managerid = hr_manager_uuids[0] if hr_manager_uuids else None

        # Prepare update data
        update_data = {
            "FirstName": data.FirstName,
            "LastName": data.LastName,
            "Email": data.User_Email.lower(),
            "Role": data.User_role,
            "Module": json.dumps(data.module),
            "User_manager": managerid,
            "HR_Manager": hr_managerid,
            "JobTitle": data.Job_Role,
            "UserTeam": json.dumps(data.Team) if isinstance(data.Team, str) else json.dumps(data.Team or []),
            "ID": user_id
        }

        try:
            print("Update data:", update_data)
            self.db.execute(update_query, update_data)
            self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
        except Exception as e:
            raise e
