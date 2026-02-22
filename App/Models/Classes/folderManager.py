from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from typing import Dict, Optional
import logging
from uuid import uuid4
from datetime import datetime
from Models.Classes.GetUser import GetUser
from Models.db.schemas import FileSchema, FolderSchema
from Models.db import models
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)


class FolderManager:
    def __init__(self, db:Session, token_info, Company_portal_Url):
        self.db = db
        self.token_info = token_info
        self.customer = self.get_tenant_info(Company_portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.is_admin = self._is_admin(token_info)
        self.setup_tables()
        GetUser(self.db, Company_portal_Url).verify_user(token_info)
        
    def setup_tables(self):
        self.tenant_table = f"{self.schema_name}.tb_{self.short_name}_tenant_info"
        self.folder = f"{self.schema_name}.tb_{self.short_name}_folders"
        self.file = f"{self.schema_name}.tb_{self.short_name}_files"
        
    def get_tenant_info(self, company_portal_url: str):
        self.Company_Portal_Url = company_portal_url
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        self.customer = user
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user
    
    def get_tenant_(self, company_portal_url: str):
        select_query = text(
            f'SELECT * FROM {self.tenant_table} WHERE "PortalURL" = :PortalURL')
        return self.db.execute(select_query, {"PortalURL": company_portal_url}).mappings().one()

    def _is_admin(self, token_info):
        print(token_info["role"])
        if token_info["role"] not in ["Admin", "Manager", "HR"]:
            return error.error("Admin privileges required", 403, "Admin Privileges Required")
        return True

    def create_folder(self, data: FolderSchema, clientuuid: Optional[str] = None):
        try:
            folder_data = data.dict()
            folder_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_Portal_Url)
            
            folder_data["EntityUUID"] = clientuuid if clientuuid is not None else str(uuid4())
            folder_data["CreatedBy"] = self.token_info["Id"]
            folder_data["UpdatedTimeAndDate"] = None
            folder_data["TenantUUID"] = tenant.TenantUUID
            if folder_data["ParentFolderID"] is not None:
                folder_data["ParentFolderUUID"] = self.get_folders(folder_data["ParentFolderID"])[0]["FolderUUID"]
            folder_data.pop("ParentFolderID")
            
            columns = ", ".join([f'"{key}"' for key in folder_data.keys()])
            values = ", ".join([f":{key}" for key in folder_data.keys()])
            
            insert_query = text(
                f'INSERT INTO {self.folder} ({columns}) VALUES ({values})'
            )
            self.db.execute(insert_query, folder_data)
            self.db.commit()
            return JSONResponse(status_code=201, content={"message": "Folder created successfully"})
        except SQLAlchemyError as e:
            logger.error(f"Error creating folder: {e}")
            raise e
        
    def get_folders(self, folder_id: int = None):
        dynamic_query = text(f'SELECT * FROM {self.folder}')
        if folder_id is not None:
            dynamic_query = text(f'{dynamic_query} WHERE "ID" = :FolderID')
        return self.db.execute(dynamic_query, {"FolderID": folder_id}).mappings().all()
    
    def get_folder_by_uuid(self, EntityUUID: str):
        dynamic_query = text(f'SELECT * FROM {self.folder} WHERE "EntityUUID" = :EntityUUID')
        return self.db.execute(dynamic_query, {"EntityUUID": EntityUUID}).mappings().all()
    
    def get_sub_folders(self, parent_folder_id: Optional[int] = None, entityType: Optional[str] = None):
        print("here",entityType)
        dynamic_query = text(f'SELECT * FROM {self.folder}')
        if entityType is not None:
            print(entityType)
            dynamic_query = text(f'{dynamic_query} WHERE "EntityType" = :EntityType')
            return self.db.execute(dynamic_query, {"EntityType": entityType}).mappings().all()
        
        parentuuid = self.get_folders(parent_folder_id)[0]["FolderUUID"]
        dynamic_query = text(f'{dynamic_query} WHERE "ParentFolderUUID" = :ParentFolderID')
        return self.db.execute(dynamic_query, {"ParentFolderID": parentuuid}).mappings().all()
    
    def create_file(self, data: FileSchema):
        try:
            file_data = data.dict()
            file_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_Portal_Url)
            
            folderuuid = self.get_folders(file_data["FolderID"])[0]["FolderUUID"]
            print(folderuuid)
            file_data.pop("FolderID")
            file_data["FolderUUID"] = folderuuid
            file_data["CreatedBy"] = self.token_info["Id"]
            file_data["UpdatedTimeAndDate"] = None
            file_data["TenantUUID"] = tenant.TenantUUID
            
            columns = ", ".join([f'"{key}"' for key in file_data.keys()])
            values = ", ".join([f":{key}" for key in file_data.keys()])
            
            insert_query = text(
                f'INSERT INTO {self.file} ({columns}) VALUES ({values})'
            )
            self.db.execute(insert_query, file_data)
            self.db.commit()
            return JSONResponse(status_code=201, content={"message": "File created successfully"})
        except SQLAlchemyError as e:
            logger.error(f"Error creating file: {e}")
            raise e
        
    def get_files_of_folder(self, folder_id: int):
        dynamic_query = text(f'SELECT * FROM {self.file} WHERE "FolderUUID" = :FolderID')
        folderuuid = self.get_folders(folder_id)[0]["FolderUUID"]
        print(folderuuid)
        return self.db.execute(dynamic_query, {"FolderID": folderuuid}).mappings().all()
            
            
            
            

            