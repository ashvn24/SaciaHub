import json
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from typing import Dict
import logging
from uuid import uuid4
from datetime import datetime
from App.Models.Classes.GetUser import GetUser
from App.Models.Classes.folderManager import FolderManager
from Models.db.schemas import FolderSchema, ProjectSchema
from Models.db import models
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)

class ProjectManager:
    def __init__(self, db: Session, token_info, Company_portal_Url):
        self.db = db
        self.token_info = token_info
        self.customer = self.get_tenant_info(Company_portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.is_admin = self._is_admin(token_info)
        self.setup_project_table()
        GetUser(self.db, Company_portal_Url).verify_user(token_info)

    def _get_project_table_name(self):
        return f"{self.schema_name}.tb_{self.short_name}_project_info"

    def setup_project_table(self):
        self.project_table = self._get_project_table_name()
        self.tenant_table = f"{self.schema_name}.tb_{self.short_name}_tenant_info"
        self.client_table = f"{self.schema_name}.tb_{self.short_name}_client_info"
        self.user_table = f"{self.schema_name}.tb_{self.short_name}_user_info"
        self.timesheet_table = f"{self.schema_name}.tb_{self.short_name}_timesheet"
        self.sow_table = f"{self.schema_name}.tb_{self.short_name}_sow_info"

    def _get_project(self, project_id: int = None, clientUUID: str = None, VendorUUID: str = None, PartnerUUID: str = None, projectuuid: str = None):
        query = f'SELECT * FROM {self.project_table}'
        params = {}
        
        if projectuuid is not None:
            query = f'{query} WHERE "ProjectUUID" = :ProjectUUID'
            params["ProjectUUID"] = projectuuid

        if clientUUID is not None:
            query += ' WHERE "ClientUUID" = :ClientUUID'
            params["ClientUUID"] = clientUUID

        if project_id is not None:
            if "WHERE" in query:
                query += ' AND "ID" = :ProjectID'
            else:
                query += ' WHERE "ID" = :ProjectID'
            params["ProjectID"] = project_id
        
        if VendorUUID is not None:
            if "WHERE" in query:
                query += ' AND "VendorUUID" = :VendorUUID'
            else:
                query += ' WHERE "VendorUUID" = :VendorUUID'
            params["VendorUUID"] = VendorUUID
        
        if PartnerUUID is not None:
            if "WHERE" in query:
                query += ' AND "PartnerUUID" = :PartnerUUID'
            else:
                query += ' WHERE "PartnerUUID" = :PartnerUUID'
            params["PartnerUUID"] = PartnerUUID

        dynamic_query = text(query)
        return self.db.execute(dynamic_query, params).mappings().all()
    
    def get_tenant_(self, company_portal_url: str):
        select_query = text(
            f'SELECT * FROM {self.tenant_table} WHERE "PortalURL" = :PortalURL')
        return self.db.execute(select_query, {"PortalURL": company_portal_url}).mappings().one()

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

    def _is_admin(self, token_info):
        print(token_info["role"])
        if token_info["role"] not in ["Admin", "Manager", "HR", "user"]:
            return error.error("Admin privileges required", 403, "Admin Privileges Required")
        return True

    def create_project(self, data: ProjectSchema):
        try:
            project_data = data.dict()
            project_data.pop("Company_Portal_Url", None)  
            tenant = self.get_tenant_(self.Company_Portal_Url)
            
            # Add UUID fields
            project_data["ProjectUUID"] = str(uuid4())
            project_data["TableUUID"] = str(uuid4())
            project_data["TenantUUID"] = tenant.TenantUUID
            project_data["CreatedBy"] = self.token_info['Id']
            project_data["CreationTimeAndDate"] = datetime.now()
            project_data["UpdatedTimeAndDate"] = None
            project_data["ProjectTimesheetBuckets"] = json.dumps(["Billable", "non-billable", "client meetings", "internal meetings", "timeoff"])

            # Get ClientUUID and ClientName based on the provided client information
            if project_data.get("ClientID") is not None:
                print("here", project_data)
                client_info = self.get_client_info(project_data.get("ClientID"))
                project_data["ClientUUID"] = client_info["ClientUUID"]
                project_data["ClientName"] = client_info["ClientName"]
            project_data.pop("ClientID", None)
                
            if project_data.get("VendorID") is not None:
                from App.Models.Classes.VendorManager import VendorManager
                vendor_info = VendorManager(self.db, self.token_info, self.Company_Portal_Url).get_vendor(project_data.get("VendorID"))[0]
                project_data["VendorUUID"] = vendor_info["VendorUUID"]
                project_data["VendorName"] = vendor_info["VendorName"]
            project_data.pop("VendorID", None)
            
            if project_data.get("PartnerID") is not None:
                from App.Models.Classes.PartnerManager import PartnerManager
                partner_info = PartnerManager(self.db, self.token_info, self.Company_Portal_Url).get_partner(project_data.get("PartnerID"))[0]
                project_data["PartnerUUID"] = partner_info["PartnerUUID"]
                project_data["PartnerName"] = partner_info["PartnerName"]
            project_data.pop("PartnerID", None)
                
            # Update schema to match database
            columns = ", ".join([f'"{k}"' for k in project_data.keys()])
            values = ", ".join([f":{k}" for k in project_data.keys()])

            insert_query = text(f'''
                INSERT INTO {self.project_table} ({columns})
                VALUES ({values})
            ''')

            self.db.execute(insert_query, project_data)
            self.db.commit()
            
            return JSONResponse(
                status_code=201,
                content={"message": "Project created successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"An unexpected error occurred during project creation: {str(e)}")
            raise e

    def get_client_info(self, client_name: str):
        try:
            query = text(f'''
                SELECT "ClientUUID", "ClientName"
                FROM {self.client_table}
                WHERE "ID" = :ClientName
            ''')
            result = self.db.execute(query, {"ClientName": client_name}).mappings().all()
            if result is None:
                return error.error("Client not found", 404, "Client Not Found")
            return result[0]
        except Exception as e:
            logger.error(f"Error fetching client info: {str(e)}")
            raise e

    def update_project(self, project_id: int, projectData: Dict):
        try:
            print(project_id)
            existing_project = self._get_project(project_id)
            print(existing_project)
            if not existing_project:
                return error.error("Project not found", 404, "Project Not Found")
                
            if isinstance(projectData, ProjectSchema):
                project_data = projectData.dict()
                project_data.pop("Company_Portal_Url", None)
            else:
                project_data = {k: v for k, v in projectData.items() if v is not None}
                
            project_data["ID"] = project_id
            project_data["UpdatedTimeAndDate"] = datetime.now()
            
            if project_data["ClientID"] is not None:
                client_info = self.get_client_info(project_data.get("ClientID"))[0]
                project_data["ClientUUID"] = client_info["ClientUUID"]
                project_data["ClientName"] = client_info["ClientName"]
            project_data.pop("ClientID", None)
            
            if project_data.get("VendorID") is not None:
                from App.Models.Classes.VendorManager import VendorManager
                vendor_info = VendorManager(self.db, self.token_info, self.Company_Portal_Url).get_vendor(project_data.get("VendorID"))[0]
                project_data["VendorUUID"] = vendor_info["VendorUUID"]
                project_data["VendorName"] = vendor_info["VendorName"]
            project_data.pop("VendorID", None)
            
            if project_data.get("PartnerID") is not None:
                from App.Models.Classes.PartnerManager import PartnerManager
                partner_info = PartnerManager(self.db, self.token_info, self.Company_Portal_Url).get_partner(project_data.get("PartnerID"))[0]
                project_data["PartnerUUID"] = partner_info["PartnerUUID"]
                project_data["PartnerName"] = partner_info["PartnerName"]
            project_data.pop("PartnerID", None)
                
            update_fields = ", ".join(
                [f'"{key}" = :{key}' for key in project_data.keys() if key != "ID"])

            update_query = text(f'''
                UPDATE {self.project_table}
                SET {update_fields}
                WHERE "ID" = :ID
            ''')

            
            self.db.execute(update_query, project_data)
            # print(existing_project)
            updated_name = project_data.get("ProjectName", "")  # The new client name to update
            existing_name = existing_project[0]["ProjectName"]
            self.update_restFields(updated_name, existing_name)
            self.db.commit()
            logger.info("Project updated successfully")
            return {"message": "Project updated successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during project update: {str(e)}")
            raise e
            
    def update_restFields(self, updated, existing):
        # Update clientName in other related tables
        print(updated, existing)
        related_tables = [self.sow_table, self.timesheet_table, self.user_table]  # Add all related table names here
        for table in related_tables:
            if table == self.user_table:
                update_related_query = text(f'''
                    UPDATE {table}
                        SET "Project" = (
                            SELECT jsonb_agg(
                                CASE 
                                    WHEN value = :existing THEN :updated
                                    ELSE value
                                END
                            )
                            FROM jsonb_array_elements_text("Project") AS value
                        )
                        WHERE "Project" @> jsonb_build_array(:existing)
                    ''')
            else:
                update_related_query = text(f'''
                    UPDATE {table}
                    SET "ProjectName" = :updated
                    WHERE "ProjectName" = :existing
                ''')
            try:
                self.db.execute(update_related_query, {"updated": updated, "existing": existing})
            except Exception as e:
                logger.error(f"Error updating table {table}: {e}")
                raise e

    def get_project(self, project_id: int = None, ClientName: int = None, VendorID: int = None, PartnerID: int = None):
        try:
            if ClientName is not None:
                client_info = self.get_client_info(ClientName)
                project = self._get_project(clientUUID = client_info["ClientUUID"])
            elif VendorID is not None:
                from App.Models.Classes.VendorManager import VendorManager
                vendor_info = VendorManager(self.db, self.token_info, self.Company_Portal_Url).get_vendor(VendorID)
                project = self._get_project(VendorUUID = vendor_info[0]["VendorUUID"])
            elif PartnerID is not None:
                from App.Models.Classes.PartnerManager import PartnerManager
                partner_info = PartnerManager(self.db, self.token_info, self.Company_Portal_Url).get_partner(PartnerID)
                project = self._get_project(PartnerUUID = partner_info[0]["PartnerUUID"])
            else:
                project = self._get_project(project_id)
                
            if not project:
                return error.error("Project not found", 404, "Project Not Found")
            
            return project
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching project: {str(e)}")
            raise e

    def delete_project(self, project_id: int):
        try:
            existing_project = self._get_project(project_id)

            if not existing_project:
                return error.error("Project not found", 404, "Project Not Found")

            delete_query = text(
                f'DELETE FROM {self.project_table} WHERE "ID" = :ProjectID')
            self.db.execute(delete_query, {"ProjectID": project_id})
            self.db.commit()

            return {"message": "Project deleted successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during project deletion: {str(e)}")
            raise e