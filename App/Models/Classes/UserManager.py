import asyncio
import json
import os
import random
import re
import string
from types import SimpleNamespace
from fastapi import HTTPException, status, Request, Response, Depends
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer
from pytz import utc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional
import logging
from Models.utils.tokenmanage import token
from Models.utils.serializer import make_serializable
from App.Models.Classes.userbgvManager import UserBGVManager
from App.Models.Classes.GetUser import GetUser
from App.Models.Classes.TenantSettings import TenantSettingsManager
from App.Models.Classes.token_authentication import blacklisted_token, decrypt_data, generate_random_password

from Models.utils.TimesheetDetails import TimesheetDetails
from Models.db import models
from Models.db.schemas import SignInSchema, ForgotPassword, UpdatePassword, resendSchema
from App.Models.Classes.token_authentication import verify_password, create_access_token, create_refresh_token, get_password_hash
from Models.utils.send_mail import send_mail_func

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
from Models.utils.error_handler import ErrorHandler

load_dotenv()

logger = logging.getLogger(__name__)
ACCESS_TOKEN_EXPIRE_MINUTES = 60
SECRET_KEY = os.getenv("SECRET_KEY")
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FROM = os.environ.get('EMAIL')
error = ErrorHandler()

class UserAuthManager:
    def __init__(self, db: Session, Company_portal_Url: Optional[str] = None):
        self.db = db
        self.restrict_hours = None
        self.two_fa_tokens = {}
        self.update_pswd = False
        if Company_portal_Url:
            self.Company_portal_Url = Company_portal_Url
            self.customer = self.get_tenant_info(Company_portal_Url)
            self.schema_name = self.customer.SchemaName
            self.short_name = self.customer.ShortName
            self.setup_user_table()
        else:
            # Handle the case when no Company_portal_Url is provided
            self.customer = None
            self.schema_name = None
            self.short_name = None

    def _get_user_schema(self, company_portal_url: str):
        user_schema = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        if user_schema is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        return user_schema

    def setup_user_table(self):
        self.user_table = f"{self.schema_name}.tb_{self.short_name}_user_info"
        self.policy_table = f"{self.schema_name}.tb_{self.short_name}_timesheet_policy"
        self.tenant_table = f"{self.schema_name}.tb_{self.short_name}_tenant_info"

    def get_tenant_info(self, company_portal_url: str):
        print("company::", company_portal_url)
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        if user is None:
            return error.error("Schema not found", 404, "Schema not found")
        return user
    
    def update_modules(self, user, modules):
        query = f"""UPDATE {self.user_table} SET "Module" = :modules WHERE "UserUUID" = :user"""
        self.db.execute(text(query), {"modules": json.dumps(modules), "user": user})
        self.db.commit()

    def _get_user(self, identifier: str):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_regex, identifier):
            query = text(f'SELECT * FROM {self.user_table} WHERE "Email" = :identifier')
        else:
            query = text(f'SELECT * FROM {self.user_table} WHERE "PhoneNumber" = :identifier')
        
        result = self.db.execute(query, {"identifier": identifier.lower()}).mappings().one_or_none()
        if not result:
            return error.error("User not found", 401, "User not found") 
        return result

    def generate_2fa_token(self, username: str, type=None) -> str:
        print(username)
        """Generate a random 4-digit OTP."""
        if type == 'tfa':
            otp = ''.join(random.choices(string.digits, k=4))
            query = text(f'UPDATE {self.user_table} SET "TwoFactorAuth" = :TwoFactorAuth, "otp_created_at" = :created_at WHERE "Email" = :Email')
        elif type == 'otp':
            print("heree")
            otp = ''.join(random.choices(string.digits, k=6))
            query = text(f'UPDATE {self.user_table} SET "otp" = :TwoFactorAuth, "otp_created_at" = :created_at WHERE "Email" = :Email')
        self.db.execute(query, {"TwoFactorAuth": otp, "created_at": datetime.now(utc),"Email": username})
        self.db.commit()
        return otp

    def send_2fa_email(self, user_email, name, token):
        """Send a 2FA verification email with a one-time token to be copied by the user."""
        send_mail_func(to=user_email, FirstName=name, password=token, subject='2fa')
        return True

    async def await_2fa_verification(self, token, email, timeout=120):
        """Wait until the token is verified within the timeout period."""
        try:
            return await asyncio.wait_for(self._check_token_verified(token, email), timeout)
        except asyncio.TimeoutError:
            return False

    async def _check_token_verified(self, token, email):
        """Check if the 2FA token is marked as verified."""
        query = text(f'SELECT "TwoFactorAuth" FROM {self.user_table} WHERE "Email" = :Email')
        stored_token = self.db.execute(query, {"Email": email}).fetchone()

        print("\n----------------Stored Token----------------:", stored_token)

        if stored_token is None:
            print(f"\n[2FA] No user found for email: {email}")
            raise "[2FA] No user found for email: {email}"
        

        stored_token = str(stored_token[0]).strip()
        input_token = str(token).strip()

        if stored_token == input_token:
            query = text(f'UPDATE {self.user_table} SET "TwoFactorAuth" = NULL WHERE "Email" = :Email')
            self.db.execute(query, {"Email": email})
            self.db.commit()
            return True
        return False

    def _create_tokens(self, user):
        access_token = create_access_token(data={"Id": str(user.UserUUID)})
        refresh_token = create_refresh_token(data={"Id": str(user.UserUUID)})
        return access_token, refresh_token

    async def signin(self, request: Request, response: Response, data: SignInSchema):
        try:

            print(self.restrict_hours)
            user = self._get_user(data.username)
            print("\n----------------User----------------:", user)
            print("\n----------------User TwoFA----------------:", user.IsTwoFA)
            if user.Status == "Inactive":
                return error.error("User is inactive", 401, "User is inactive")

            if not verify_password(data.password, user.Password):
                return error.error("Invalid email or password", 401, "Invalid email or password")
                
            if user.sso_active:
                return {
                    "message":"Your SSO is active. Please log in with Microsoft SSO."
                }
            if user.IsTwoFA == True:
                res = self.set_twofa_exp(user.UserUUID)
                print("Result", res)
                if not res:
                    two_fa_token = self.generate_2fa_token(user.Email, 'tfa')
                    self.send_2fa_email(data.username, user.FirstName, two_fa_token)
                    return {
                        "message": "2FA verification required"
                    } 

            return await self._create_response(user, data)

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during sign-in: {str(e)}")
            raise e

    def signout(self, authtoken: str):
        try:
            # Add the token to the blacklist
            blacklisted_token.add(authtoken["jti"])
            token(self.db, self.Company_portal_Url).updatetoken(authtoken["Id"], None)
            return {"message": "Sign-out successful"}
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during sign-out: {str(e)}")
            raise e

    def refresh_token(self, token_info: Dict):
        try:
            if token_info is None:
                return error.error("Invalid refresh token", 401, "Invalid refresh token")

            access_token = create_access_token(
                data={"Id": str(
                    token_info["Id"]), "role": token_info["role"], "hours": token_info["hours"]},
                expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            )

            return {"message": "Token refreshed successfully", "access_token": access_token}
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during token refresh: {str(e)}")
            raise e

    def update_profile(self, data: str = None, toggle: str = None, token_info: Dict = None):
        try:
            existing_user = self._get_user_by_uuid(token_info["Id"])
            if not existing_user:
                return {"message": "User not found"}, 404
            if data:
                self._update_profile_picture(token_info["Id"], data)
            elif toggle == "twoFa/":
                self._twoFactorToggle(token_info["Id"])
            return {"message": "Profile updated successfully"}

        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            raise sql_exc
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e

    def forgot_password(self, data: ForgotPassword):
        try:
            user_details = self._get_user(data.Email)
            if not user_details:
                return error.error("Email does not exist", 404, "Email does not exist")
            if user_details["Status"] != "Active":
                return error.error("User not Active", 404, "User not Active")
            # new_password = generate_random_password()
            # self._update_password(data.Email, new_password)
            otp = self.generate_2fa_token(user_details["Email"], 'otp')
            print("here")
            send_mail_func(to=data.Email, FirstName=user_details.FirstName, password=otp, subject='reset',company_portal_url=None)
            return {"message": "Request created"}

        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            raise sql_exc
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e
            
    def verify_otp(self, token, email):
        try:
            token = int(token)
            user = self._get_user(email)
            createdAt = user["otp_created_at"].replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > createdAt + timedelta(minutes=1):
                return error.error("otp expired", 400, "otp expired")
            query = text(f'SELECT "otp" FROM {self.user_table} WHERE "Email" = :Email')
            stored_token = self.db.execute(query, {"Email": email}).fetchone()[0]

            if stored_token and stored_token == token:
                query = text(f'UPDATE {self.user_table} SET "otp" = NULL WHERE "Email" = :Email')
                self.db.execute(query, {"Email": email})
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e
            
    def resend_mail_or_otp(self, data:resendSchema, mail:str):
        user = self._get_user(data.email)
        if mail == "otp":
            otp = self.generate_2fa_token(user["Email"], 'otp')
            send_mail_func(to=data.email, FirstName=user["FirstName"], password=otp, subject='reset',company_portal_url=f"{self.short_name}.saciahub.com")
        elif mail == "mail":
            send_mail_func(
            data.email,
            FirstName=user["FirstName"],
            password=create_access_token({"user":data.email}, expires_delta=timedelta(minutes=15)),
            subject="welcome",
            company_portal_url=f"{self.short_name}.saciahub.com"
        )
        elif mail == "tfa":
            otp = self.generate_2fa_token(user["Email"], 'tfa')
            send_mail_func(to=data.email, FirstName=user["FirstName"], password=otp, subject='2fa',company_portal_url=f"{self.short_name}.saciahub.com")
        return JSONResponse(
            status_code=200,
            content={"message":"mail sent"}
        )

    def update_password(self, data: UpdatePassword, token_info: Dict):
        try:
            self.update_pswd = True
            existing_user = self._get_user_by_uuid(token_info["Id"])
            if not existing_user:
                return {"message": "User not found"}, 404

            if not verify_password(data.old_password, existing_user.Password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid old password",
                )

            self._update_password(existing_user.Email, data.new_password)
            return {"message": "Password updated successfully"}

        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            raise sql_exc
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise e

    # Helper methods
    def _get_policy(self, client):
        # Handle empty client list
        if not client:
            return None
        
        select_query = text(
            f'SELECT * FROM {self.policy_table} WHERE "TimesheetClient" = ANY(:client)')
        policy = self.db.execute(
            select_query, {"client": list(client)}).mappings().all()
        policyData = [
            {
                "Timesheet_template": row.get('Timesheet_template'),
                "TimesheetClient": row.get("TimesheetClient"),
                "Timesheet_fields": row.get('Timesheet_fields'),
                "Timesheet_week_day_start": row.get("Timesheet_week_day_start"),
                "Timesheet_week_day_end": row.get('Timesheet_week_day_end'),
                "Timesheet_restrict_hours": row.get('Timesheet_restrict_hours'),
                "Timesheet_min_restrict_hours": row.get('Timesheet_min_restrict_hours'),
                "Timesheet_week_time_end": row.get('Timesheet_week_time_end').strftime('%H:%M:%S') if row.get('Timesheet_week_time_end') else None,
                "Timesheet_month_end_day": row.get('Timesheet_month_end_day'),
                "Timesheet_month_day_time": row.get('Timesheet_month_day_time').strftime('%H:%M:%S') if row.get('Timesheet_month_day_time') else None,
                "Timesheet_month_rollover_days": row.get('Timesheet_month_rollover_days')
            }
            for row in policy
        ] if policy else None

        return policyData

    def _get_manager_name(self, manager_id: str):
        if manager_id:
            manager_query = text(f'SELECT "FirstName" FROM {self.user_table} WHERE "UserUUID" = :User_manager')
            manager_result = self.db.execute(manager_query, {"User_manager": manager_id}).fetchone()
            return manager_result[0] if manager_result else None
        return None

    def _update_first_time_login(self, username: str):
        update_query = text(f'UPDATE {self.user_table} SET "First_time_login" = :First_time_login WHERE "Username" = :Username')
        self.db.execute(update_query, {"First_time_login": False, "Username": username})
        self.db.commit()

    def _create_tokens(self, user):
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"Id": str(user.UserUUID), "role": user.Role, "hours": self.restrict_hours},
            expires_delta=access_token_expires,
        )
        refresh_token = create_refresh_token(
            data={"Id": str(user.UserUUID), "role": user.Role, "hours": self.restrict_hours}
        )
        return access_token, refresh_token
    

    async def notifications(self, Company_Portal_Url: str):
        tenant_settings = TenantSettingsManager(self.db, self.Company_portal_Url)
        request_notification = await tenant_settings.is_request_notification_enabled()
        timesheet_notification = await tenant_settings.is_timesheet_notification_enabled()
        return {
            "request_notification": request_notification,
            "timesheet_notification": timesheet_notification
        }
        
    async def _create_response(self, user, data): #removed data
        policy =None
        manager_first_name = None
        if user.Client is not None:
            policy = self._get_policy(user.Client)
            if policy: 
                self.restrict_hours = policy[0]['Timesheet_min_restrict_hours'] if policy is not None else 9
        if user.User_manager is not None: manager_first_name = self._get_manager_name(user.User_manager)
        first_time_login = user.First_time_login
        job_role = user.JobTitle
        if first_time_login: self._update_first_time_login(user.Email)
        access_token, refresh_token = self._create_tokens(user)
        print("Access Token:", access_token)
        print("Refresh Token:", refresh_token)
        token(self.db, self.Company_portal_Url).updatetoken(user.UserUUID, access_token)
        token_created = datetime.now().isoformat()
        timesheet = TimesheetDetails(self.customer, self.db)
        result = timesheet.get_timesheet_details(user.UserUUID)
        if user.Role == 'Admin':
            notifications = await self.notifications(self.Company_portal_Url)
        else:
            notifications = None
        
        # self.sortProjects(user, result)
        try:
            bgvData = UserBGVManager(self.db, self.Company_portal_Url).get_user_bgv(str(user.UserUUID))
            bgv_Data = make_serializable(bgvData)
        except Exception as e:
            bgv_Data = {}
        return {
            "message": "Sign-in successful",
            "UserUUID": str(user.UserUUID),
            "Role": user.Role,
            "JobRole": job_role,
            "UserId": user.User_Id,
            "UserName": user.Email,
            "UserManager": manager_first_name,
            "TimeSheetDetails": result,
            "FirstName": user.FirstName,
            "LastName": user.LastName,
            "UserbgvCompleted": user.User_bgv,
            "UserGroup": user.UserGroup,
            "UserTeam": user.UserTeam,
            "Permissions": None,
            "ActiveModule": user.Module,
            "TimesheetPolicy": policy,
            "TokenExpiry": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "TokenCreated": token_created,
            "FirstTimeLogin": first_time_login,
            "profilePictureURL": user.ProfilePictureURL,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "bgvData": bgv_Data,
            "2FA": user.IsTwoFA,
            "request_notification": notifications["request_notification"] if user.Role == 'Admin' else None,
            "timesheet_notification": notifications["timesheet_notification"] if user.Role == 'Admin' else None,
        }
    def sortProjects(self, user, result):
        for data in result:
            filtered_projects = [i for i in data['projects'] if i['name'] in user.Project]
            data['projects'] = filtered_projects

    def _get_user_by_uuid(self, user_uuid: str):
        dynamic_query = text(f'SELECT * FROM {self.user_table} WHERE "UserUUID" = :UserUUID')
        return self.db.execute(dynamic_query, {"UserUUID": user_uuid}).mappings().one_or_none()

    def _update_profile_picture(self,  user_uuid: str, profile_picture_url: str):
        update_query = text(f'UPDATE {self.user_table} SET "ProfilePictureURL" = :ProfilePictureURL WHERE "UserUUID" = :UserUUID')
        self.db.execute(update_query, {"UserUUID": user_uuid, "ProfilePictureURL": profile_picture_url})
        self.db.commit()

    def _twoFactorToggle(self, user_uuid: str):
        query = text(f'''
            UPDATE {self.user_table}
            SET "IsTwoFA" = CASE WHEN "IsTwoFA" = TRUE THEN FALSE ELSE TRUE END
            WHERE "UserUUID" = :user_uuid
        ''')
        try:
            self.db.execute(query, {"user_uuid": user_uuid})
            self.db.commit()  # Ensure the transaction is committed
        except SQLAlchemyError as e:
            print(f"Error in _twoFactorToggle: {e}")
            self.db.rollback()  # Rollback in case of error to prevent transaction issues
            raise

    def _update_password(self, identifier: str, new_password: str):
        try:
            hashed_password = get_password_hash(new_password)
            update_query = text(f'''
                UPDATE {self.user_table}
                SET "Password" = :password, "First_time_login" = :login
                WHERE "Email" = :email
            ''')

            self.db.execute(
                update_query,
                {"password": hashed_password,
                    "login": True if not self.update_pswd else False, "email": identifier}
            )
            self.db.commit()
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error occurred: {str(e)}")
            raise e

    def impersonate_role(self, Company_Portal_Url: str, token_info: Dict, user_id: int):
        try:
            if token_info['role'] != "Admin":
                return error.error("Requires admin privileges", 400, "Bad Request")
            user = GetUser(self.db, Company_Portal_Url)
            print("here")
            user_info = user.get_user_uuids([str(user_id)])
            user_data = self._get_user_by_uuid(user_info[0])
            access_token, refresh_token = self._create_tokens(user_data)
            token(self.db, self.Company_portal_Url).updatetoken(user_info[0], access_token)
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Refresh-Token": refresh_token,
            }
            return JSONResponse(
                content="Impersonation successful",
                status_code=status.HTTP_200_OK,
                headers=headers,
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during impersonation: {str(e)}")
            raise e
            
    
    def get_msal_connetion(self, tenantid):
        query = text(f"""SELECT * FROM {self.tenant_table} WHERE "TenantUUID" = :tenantid""")
        result = self.db.execute(query, {"tenantid": str(tenantid)}).fetchone()
        if not result:
            response_contect = {
                "sucess": False,
                "message": "Tennat Details Are Not Present In Db",
                "status_code": 400
            }
            return response_contect
        if not result.sso_active:
            response_contect = {
                "sucess": False,
                "message": "Tennat Sso Is Not Active",
                "status_code": 400
            }
            return response_contect
        AUTHORITY = f'https://login.microsoftonline.com/{result.ms_tenant_id}'
        response_contect = {
            "sucess": True,
            "result": result,
            "AUTHORITY" : AUTHORITY
        }
        return response_contect
    

    def set_twofa_exp(self, uid):
        query = text(f"""SELECT twofa_expiry FROM {self.user_table} WHERE "UserUUID" = :uid""")
        result = self.db.execute(query, {"uid":uid}).mappings().one_or_none()
        if result is not None and result['twofa_expiry'] is not None and result['twofa_expiry'] > datetime.now(utc):
            return True
        else:
            query = text(f"""UPDATE {self.user_table} SET "twofa_expiry" = :exp WHERE "UserUUID" = :uid""")
            self.db.execute(query, {"uid": uid, "exp": datetime.now(utc) + timedelta(hours=1)})
            self.db.commit()
            return False
        