from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict
from sqlalchemy import text
import logging
from App.Models.Classes.GetUser import GetUser
from Models.db import models
from Models.db.s3Storage import handle_image_in_spaces
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)


def handle_exception(logger, status_code, detail):
    logger.error(detail)
    raise HTTPException(status_code=status_code, detail=detail)


class MediaManager:
    def __init__(self, db: Session, token_info: Dict, company_portal_url: str):
        self.db = db
        self.token_info = token_info
        self.company_portal_url = company_portal_url
        self.user = None
        self.company_schema_name = None
        self.company_shortname = None
        self.user_table_name = None
        GetUser(self.db, company_portal_url).verify_user(token_info)

        try:
            self._set_user_info()
        except HTTPException as exc:
            handle_exception(logger, exc.status_code, exc.detail)
        except Exception as e:
            handle_exception(logger, 500, "Server error during initialization")

    def _set_user_info(self):
        """Fetch the user information based on the company portal URL"""
        self.user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == self.company_portal_url)
            .first()
        )
        if not self.user:
            handle_exception(logger, 404, "User not found")

        self.company_schema_name = self.user.SchemaName
        self.company_shortname = self.user.ShortName
        self.user_table_name = f"{self.company_schema_name}.tb_{
            self.company_shortname}_user_info"
        logger.info(f"User table name: {self.user_table_name}")

    def _get_existing_user_email(self, user=None):
        """
        Retrieve existing user email from the dynamically constructed table
        
        Args:
            user (str, optional): User UUID. If duplicated, takes first 36 chars.
            
        Returns:
            Row: Database row containing user information
            
        Raises:
            HTTPException: If user not found or database error occurs
        """
        try:
            # Clean up user UUID if provided
            if user is not None:
                # Take only first 36 characters if UUID is duplicated
                if len(user) > 36:
                    user = user[:36]
                user_uuid = user
            else:
                user_uuid = self.token_info["Id"]

            # Log the query parameters
            logger.info(f"Searching for user with UUID: {user_uuid}")
            
            # Construct and execute query
            dynamic_query_email = text(
                f'SELECT * FROM {self.user_table_name} WHERE "UserUUID" = :UserUUID'
            )
            existing_user_email = self.db.execute(
                dynamic_query_email, {"UserUUID": user_uuid}
            ).fetchone()

            if not existing_user_email:
                logger.error(f"User not found with UUID: {user_uuid}")
                return error.error("User not found", 404, "User Not Found")

            return existing_user_email

        except HTTPException as e:
            raise e
        except Exception as e:
            raise e

    async def upload_media(self, files: List[UploadFile], user: str = None, extract: int = None):
        """Handle media upload logic"""
        try:
            existing_user_email = self._get_existing_user_email(user)
            filename = existing_user_email.UserUUID
            file_keys = []
            print("\n exis", existing_user_email, "\n user", user, "filename:", filename)
            for file in files:
                file_key = await handle_image_in_spaces(
                    "upload",
                    file_data=file,
                    file_name=f"{filename}",
                    folder=self.company_shortname,
                    extract=extract
                )
                if file_key:
                    file_keys.append(file_key)

            if not file_keys:
                return error.error("No files were successfully uploaded", 400, "No Files Uploaded")

            return {"file_keys": file_keys}

        except HTTPException as exc:
            raise exc
        except Exception as e:
            raise e

    async def get_media(self, file_name: str, user: str = None):
        """
        Handle media retrieval logic
        
        Args:
            file_name (str): Name of the file to retrieve
            user (str, optional): User UUID. Defaults to None.
        
        Returns:
            str: URL of the retrieved media
            
        Raises:
            HTTPException: If any error occurs during media retrieval
        """
        print("\n file_name", file_name, "\n user", user)
        try:
            # Validate inputs
            if not file_name:
                return error.error("File name is required", 400, "File Name Required")

            # Get user information
            existing_user_email = self._get_existing_user_email(user)
            if not existing_user_email:
                return error.error("User not found", 404, "User Not Found")

            filename = existing_user_email.UserUUID
            folder = f'{self.company_shortname}/{filename}'
            
            logger.info(f"Attempting to retrieve file: {file_name} from folder: {folder}")
            
            # Get file URL from storage
            file_key = await handle_image_in_spaces(
                "get_url", 
                folder=folder, 
                file_name=file_name
            )

            if not file_key:
                logger.error(f"File not found: {file_name} in folder: {folder}")
                return error.error("File not found", 404, "File Not Found")

            return file_key

        except HTTPException as exc:
            print("Error:", exc.detail)
            logger.error(f"HTTP error during media retrieval: {exc.detail}")
            raise exc
        except Exception as e:
            logger.error(f"Unexpected error during media retrieval: {str(e)}")
            print("Error:", str(e))
            raise e

    async def handle_exception(self, request, exc):
        """Handle exceptions and return error response"""
        status_code = exc.status_code if isinstance(
            exc, HTTPException) else 500
        detail = exc.detail if isinstance(
            exc, HTTPException) else "Server error"
        logger.error(detail)
        return JSONResponse(status_code=status_code, content={"error": detail})
