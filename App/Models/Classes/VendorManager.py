from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from typing import Dict
import logging
from uuid import uuid4
from datetime import datetime
from Models.Classes.GetUser import GetUser
from Models.Classes.folderManager import FolderManager
from Models.Classes.ProjectManager import ProjectManager
from Models.Classes.SOWManager import SOWManager
from Models.db.schemas import FolderSchema, VendorSchema
from Models.db import models
from uuid import UUID
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()

logger = logging.getLogger(__name__)


class VendorManager:
    def __init__(self, db: Session, token_info, Company_portal_Url):
        self.db = db
        self.token_info = token_info
        self.customer = self.get_tenant_info(Company_portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.is_admin = self._is_admin(token_info)
        self.setup_vendor_table()
        GetUser(self.db, Company_portal_Url).verify_user(token_info)

    def _get_vendor_table_name(self):
        return f"{self.schema_name}.tb_{self.short_name}_vendor_info"

    def setup_vendor_table(self):
        self.vendor_table = self._get_vendor_table_name()
        self.tenant_table = f"{self.schema_name}.tb_{
            self.short_name}_tenant_info"
        self.project_table = f"{self.schema_name}.tb_{
            self.short_name}_project_info"
        self.sow_table = f"{self.schema_name}.tb_{
            self.short_name}_sow_info"

    def _get_vendor(self, vendor_id: int = None):
        # Build a single query that joins through the UUIDs to grab the integer IDs
        query = f'''
            SELECT
                v.*,
                proj."ID"   AS "ProjectID",
                s."ID"      AS "SOWID"
            FROM {self.vendor_table} AS v
            LEFT JOIN {self.project_table} AS proj
                ON v."ProjectAssigned" = proj."ProjectUUID"
            LEFT JOIN {self.sow_table} AS s
                ON v."SOWAssigned"     = s."SOWUUID"
        '''
        params = {}

        if vendor_id is not None:
            query += '\n WHERE v."ID" = :VendorID'
            params["VendorID"] = vendor_id

        return self.db.execute(text(query), params).mappings().all()


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
            return error.error("Schema not found", 404, "Not Found")
        return user

    def _is_admin(self, token_info):
        if "role" not in token_info or token_info["role"] not in ["Admin", "Manager"]:
            return error.error("Admin privileges required", 403, "Forbidden")
        return True

    def create_vendor(self, data: VendorSchema):
        try:
            vendor_data = data.dict()
            vendor_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_Portal_Url)

            # Store and remove lists from vendor_data
            project_ids = vendor_data.pop("ProjectAssigned", [])
            sow_ids = vendor_data.pop("SOWAssigned", [])
            
            projectManager = ProjectManager(
                self.db, self.token_info, self.Company_Portal_Url)
            sowManager = SOWManager(
                self.db, self.token_info, self.Company_Portal_Url)
            
            # Get UUIDs without string formatting
            project_uuids = [projectManager._get_project(project_id=pid)[0]['ProjectUUID'] for pid in project_ids]
            sow_uuids = [sowManager._get_sow(sow_id=sid)[0]['SOWUUID'] for sid in sow_ids]
            
            # Add UUID fields
            vendor_data["VendorID"] = models.generate_user_id()
            vendor_data["VendorUUID"] = str(uuid4())
            vendor_data["TableUUID"] = str(uuid4())
            vendor_data["TenantUUID"] = tenant.TenantUUID
            vendor_data["CreatedBy"] = self.token_info['Id']
            vendor_data["CreationTimeAndDate"] = datetime.now()
            vendor_data["UpdatedTimeAndDate"] = None
            vendor_data["ProjectAssigned"] = project_uuids[0] if project_uuids else None  # Store single UUID
            vendor_data["SOWAssigned"] = sow_uuids[0] if sow_uuids else None  # Store single UUID

            # Insert vendor
            columns = ", ".join([f'"{k}"' for k in vendor_data.keys()])
            values = ", ".join([f":{k}" for k in vendor_data.keys()])

            insert_query = text(f'''
                INSERT INTO {self.vendor_table} ({columns})
                VALUES ({values})
            ''')

            self.db.execute(insert_query, vendor_data)

            # Update projects
            projectManager = ProjectManager(self.db, self.token_info, self.Company_Portal_Url)
            for project_id in project_ids:
                try:
                    project_result = projectManager._get_project(project_id=project_id)
                    if not project_result:
                        logger.error(f"Project with ID {project_id} not found.")
                        continue
                    
                    project_uuid = project_result[0]
                    project_update_data = {
                        "ID": project_uuid["ID"],
                        "VendorName": vendor_data["VendorName"],
                        "VendorUUID": vendor_data["VendorUUID"],
                        "ProjectUUID": project_uuid["ProjectUUID"],
                        "ProjectName": project_uuid["ProjectName"],
                        "ProjectStartDate": project_uuid["ProjectStartDate"],
                        "ProjectEndDate": project_uuid["ProjectEndDate"],
                        "ProjectTimesheetBuckets": project_uuid["ProjectTimesheetBuckets"],
                        "TableUUID": project_uuid["TableUUID"],
                        "TenantUUID": project_uuid["TenantUUID"],
                        "ClientUUID": project_uuid["ClientUUID"],
                        "ClientName": project_uuid["ClientName"],
                        "UsersAssigned": project_uuid["UsersAssigned"],
                        "UpdatedTimeAndDate": datetime.now()
                    }

                    projectManager.update_project(
                        project_id=project_uuid["ID"],
                        projectData=project_update_data
                    )
                except Exception as e:
                    logger.error(f"Error updating project {project_id}: {str(e)}")
                    continue

            # Update SOWs
            sowManager = SOWManager(self.db, self.token_info, self.Company_Portal_Url)
            for sow_id in sow_ids:
                try:
                    sow_result = sowManager._get_sow(sow_id=sow_id)
                    if not sow_result:
                        logger.error(f"SOW with ID {sow_id} not found.")
                        continue
                    
                    sow_uuid = sow_result[0]
                    sow_update_data = {
                        "ID": sow_uuid["ID"],
                        "VendorName": vendor_data["VendorName"],
                        "VendorUUID": vendor_data["VendorUUID"],
                        "SOWUUID": sow_uuid["SOWUUID"],
                        "ProjectUUID": sow_uuid["ProjectUUID"],
                        "TableUUID": sow_uuid["TableUUID"],
                        "TenantUUID": sow_uuid["TenantUUID"],
                        "UpdatedTimeAndDate": datetime.now()
                    }

                    sowManager.update_sow(
                        sow_id=sow_uuid["ID"],
                        sowdata=sow_update_data
                    )
                except Exception as e:
                    logger.error(f"Error updating SOW {sow_id}: {str(e)}")
                    continue

            self.db.commit()
            return JSONResponse(
                status_code=201,
                content={"message": "Vendor created successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            return error.error("Database error occurred", 500, "Internal Server Error")
        except Exception as e:
            logger.error(f"An unexpected error occurred during vendor creation: {str(e)}")
            return e

    def update_vendor(self, vendor_id: int, vendor_data: Dict):
        try:
            existing_vendor = self._get_vendor(vendor_id)
            if not existing_vendor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found"
                )

            # Convert to dict if it's a Pydantic model
            if hasattr(vendor_data, 'dict'):
                vendor_data = vendor_data.dict()

            # Remove portal URL if present
            vendor_data.pop("Company_Portal_Url", None)

            # Store and remove lists from vendor_data
            project_ids = vendor_data.pop("ProjectAssigned", [])
            sow_ids = vendor_data.pop("SOWAssigned", [])

            # Managers
            projectManager = ProjectManager(self.db, self.token_info, self.Company_Portal_Url)
            sowManager = SOWManager(self.db, self.token_info, self.Company_Portal_Url)

            # Convert project and SOW IDs to UUIDs (first one to store in vendor table)
            project_uuids = []
            for pid in project_ids:
                project_result = projectManager._get_project(project_id=pid)
                if project_result:
                    project_uuids.append(project_result[0]["ProjectUUID"])
            
            sow_uuids = []
            for sid in sow_ids:
                sow_result = sowManager._get_sow(sow_id=sid)
                if sow_result:
                    sow_uuids.append(sow_result[0]["SOWUUID"])

            vendor_data["ProjectAssigned"] = project_uuids[0] if project_uuids else None
            vendor_data["SOWAssigned"] = sow_uuids[0] if sow_uuids else None

            # Add update metadata
            vendor_data["ID"] = vendor_id
            vendor_data["UpdatedTimeAndDate"] = datetime.now()

            # Update vendor info
            update_fields = ", ".join(
                [f'"{key}" = :{key}' for key in vendor_data.keys() if key != "ID"]
            )

            update_query = text(f'''
                UPDATE {self.vendor_table}
                SET {update_fields}
                WHERE "ID" = :ID
            ''')

            self.db.execute(update_query, vendor_data)

            # Update related projects
            for pid in project_ids:
                project_result = projectManager._get_project(project_id=pid)
                if not project_result:
                    logger.error(f"Project with ID {pid} not found.")
                    continue

                project_uuid = project_result[0]
                project_update_data = {
                    "VendorName": vendor_data.get("VendorName", existing_vendor[0]["VendorName"]),
                    "VendorUUID": existing_vendor[0]["VendorUUID"],
                    "ClientID": project_uuid.get("ClientID"),
                    "ClientUUID": project_uuid.get("ClientUUID"),
                    "ClientName": project_uuid.get("ClientName"),
                    "ProjectName": project_uuid.get("ProjectName"),
                    "ProjectUUID": project_uuid.get("ProjectUUID"),
                    "TableUUID": project_uuid.get("TableUUID"),
                    "TenantUUID": project_uuid.get("TenantUUID"),
                    "ID": project_uuid.get("ID"),
                    "UpdatedTimeAndDate": datetime.now()
                }

                try:
                    projectManager.update_project(
                        project_id=project_uuid["ID"],
                        projectData=project_update_data
                    )
                except Exception as e:
                    logger.error(f"Error updating project {pid}: {str(e)}")
                    continue

            # Update related SOWs
            for sid in sow_ids:
                sow_result = sowManager._get_sow(sow_id=sid)
                if not sow_result:
                    logger.error(f"SOW with ID {sid} not found.")
                    continue

                sow_uuid = sow_result[0]
                sow_update_data = {
                    "VendorName": vendor_data.get("VendorName", existing_vendor[0]["VendorName"]),
                    "VendorUUID": existing_vendor[0]["VendorUUID"],
                    "ProjectID": sow_uuid.get("ProjectID"),
                    "ProjectUUID": sow_uuid.get("ProjectUUID"),
                    "TableUUID": sow_uuid.get("TableUUID"),
                    "TenantUUID": sow_uuid.get("TenantUUID"),
                    "ID": sow_uuid.get("ID"),
                    "UpdatedTimeAndDate": datetime.now()
                }

                try:
                    sowManager.update_sow(
                        sow_id=sow_uuid["ID"],
                        sowdata=sow_update_data
                    )
                except Exception as e:
                    logger.error(f"Error updating SOW {sid}: {str(e)}")
                    continue

            self.db.commit()
            return {"message": "Vendor updated successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"An unexpected error occurred during vendor update: {str(e)}")
            raise e

    def get_vendor(self, vendor_id: int = None, ):
        try:
            vendor = self._get_vendor(vendor_id)
            if not vendor:
                return error.error("Vendor not found", 404, "Not Found")

            return vendor
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while fetching vendor: {str(e)}")
            raise e

    def delete_vendor(self, vendor_id: int):
        try:
            existing_vendor = self._get_vendor(vendor_id)

            if not existing_vendor:
                return error.error("Vendor not found", 404, "Not Found")

            delete_query = text(
                f'DELETE FROM {self.vendor_table} WHERE "ID" = :VendorID')
            self.db.execute(delete_query, {"VendorID": vendor_id})
            self.db.commit()

            return {"message": "Vendor deleted successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during vendor deletion: {str(e)}")
            raise e

