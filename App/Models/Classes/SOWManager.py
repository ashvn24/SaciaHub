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
from Models.Classes.GetUser import GetUser
from Models.Classes.folderManager import FolderManager
from Models.db.schemas import FolderSchema, SOWSchema
from Models.db import models
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)

class SOWManager:
    def __init__(self, db: Session, token_info, Company_portal_Url):
        self.db = db
        self.token_info = token_info
        self.customer = self.get_tenant_info(Company_portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.is_admin = self._is_admin(token_info)
        self.setup_sow_table()
        GetUser(self.db, Company_portal_Url).verify_user(token_info)

    def setup_sow_table(self):
        self.sow_table = f"{self.schema_name}.tb_{self.short_name}_sow_info"
        self.tenant_table = f"{self.schema_name}.tb_{self.short_name}_tenant_info"
        self.project_table = f"{self.schema_name}.tb_{self.short_name}_project_info"
        self.client_table = f"{self.schema_name}.tb_{self.short_name}_client_info"
        self.user_table = f"{self.schema_name}.tb_{self.short_name}_user_info"
        self.vendor_table = f"{self.schema_name}.tb_{self.short_name}_vendor_info"
        self.timesheet_table = f"{self.schema_name}.tb_{self.short_name}_timesheet"

    def _get_sow(self, sow_id: int = None, projectUUID: str = None, clientUUID: str = None, vendorUUID: str = None, partnerUUID: str = None, sowuuid: str =None):
        query =f'''
                SELECT 
                    sow.*,
                    u."ID" AS "ClientRepresentiveID",
                    COALESCE(u."FirstName" || ' ' || u."LastName", '') AS "ClientRepresentive"
                FROM {self.sow_table} AS sow
                LEFT JOIN {self.user_table} AS u ON sow."ClientRepresentive" = u."UserUUID"
            '''

        params = {}
        
        if sowuuid is not None:
            query = f'{query} WHERE sow."SOWUUID" = :SOWUUID'
            params["SOWUUID"] = sowuuid
            
        if projectUUID is not None:
            query = f'{query} WHERE sow."ProjectUUID" = :ProjectUUID'
            params["ProjectUUID"] = projectUUID
            
        if sow_id is not None:
            if "WHERE" in query:
                query = f'{query} AND sow."ID" = :SOWID'
            else:
                query = f'{query} WHERE sow."ID" = :SOWID'
            params["SOWID"] = sow_id
        
        if clientUUID is not None:
            if "WHERE" in query:
                query = f'{query} AND sow."ClientUUID" = :ClientUUID'
            else:
                query = f'{query} WHERE sow."ClientUUID" = :ClientUUID'
            params["ClientUUID"] = clientUUID
            
        if vendorUUID is not None:
            print(vendorUUID)
            if "WHERE" in query:
                query = f'{query} AND sow."VendorUUID" = :VendorUUID'
            else:
                query = f'{query} WHERE sow."VendorUUID" = :VendorUUID'
            params["VendorUUID"] = vendorUUID
        
        if partnerUUID is not None:
            if "WHERE" in query:
                query = f'{query} AND sow."PartnerUUID" = :PartnerUUID'
            else:
                query = f'{query} WHERE sow."PartnerUUID" = :PartnerUUID'
            params["PartnerUUID"] = partnerUUID
            
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
            return error.error("Schema not found", 404, "Tenant Info")
        return user

    def _is_admin(self, token_info):
        if "role" not in token_info or token_info["role"] not in ["Admin", "Manager", "HR", "user"]:
            return error.error("Admin privileges required", 403, "Admin Privileges Required")
        return True
    
    def create_sow(self, data: SOWSchema):
        try:
            sow_data = data.dict()
            sow_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_Portal_Url)
            
            # Add UUID fields
            sow_data["SOWUUID"] = str(uuid4())
            sow_data["TableUUID"] = str(uuid4())
            sow_data["TenantUUID"] = tenant.TenantUUID
            sow_data["CreatedBy"] = self.token_info['Id']
            sow_data["CreationTimeAndDate"] = datetime.now()
            sow_data["UpdatedTimeAndDate"] = None

            # Get ProjectUUID and ProjectName based on the provided project information
            project_info = self.get_project_info(sow_data.get("ProjectID"))
            sow_data["ProjectUUID"] = project_info["ProjectUUID"]
            sow_data["ProjectName"] = project_info["ProjectName"]
            sow_data.pop("ProjectID", None)

            # Get ClientUUID and ClientName based on the provided client information
            if sow_data.get("ClientID") is not None:
                client_info = self.get_client_info(sow_data.get("ClientID"))
                print(client_info)
                sow_data["ClientUUID"] = client_info["ClientUUID"]
                sow_data["ClientName"] = client_info["ClientName"]
            sow_data.pop("ClientID", None)
            
            if sow_data.get("VendorID") is not None:
                vendor_info = self.get_vendor_info(sow_data.get("VendorID"))
                sow_data["VendorUUID"] = vendor_info["VendorUUID"]
                sow_data["VendorName"] = vendor_info["VendorName"]
            sow_data.pop("VendorID", None)
            
            if sow_data.get("PartnerID") is not None:
                from Models.Classes.PartnerManager import PartnerManager
                partner_info = PartnerManager(self.db, self.token_info, self.Company_Portal_Url).get_partner(sow_data.get("PartnerID"))[0]
                sow_data["PartnerUUID"] = partner_info["PartnerUUID"]
                sow_data["PartnerName"] = partner_info["PartnerName"]
            sow_data.pop("PartnerID", None)
            user_info = self.get_user_info(sow_data.get("ClientRepresentive"))
            sow_data["ClientRepresentive"] = user_info["UserUUID"]

            columns = ", ".join([f'"{k}"' for k in sow_data.keys()])
            values = ", ".join([f":{k}" for k in sow_data.keys()])

            insert_query = text(f'''
                INSERT INTO {self.sow_table} ({columns})
                VALUES ({values})
            ''')

            self.db.execute(insert_query, sow_data)
            self.db.commit()
            
            # if sow_data.get("ClientUUID") is not None:
            #     folder_data = FolderManager(self.db, self.token_info, self.Company_Portal_Url)
            #     folderId = folder_data.get_folder_by_uuid(sow_data["ClientUUID"])[0]["ID"]
            #     folder_data.create_folder(
            #         data = FolderSchema(
            #             FolderName=sow_data["SOWName"],
            #             ParentFolderID=folderId,
            #             EntityType="SOW"
            #         )
            #     )
            #     logging.info("Folder created successfully")
                
            # if sow_data.get("VendorUUID") is not None:
            #     folder_data = FolderManager(self.db, self.token_info, self.Company_Portal_Url)
            #     folderId = folder_data.get_folder_by_uuid(sow_data["VendorUUID"])[0]["ID"]
            #     folder_data.create_folder(
            #         data = FolderSchema(
            #             FolderName=sow_data["SOWName"],
            #             ParentFolderID=folderId,
            #             EntityType="SOW"
            #         )
            #     )
            #     logging.info("Folder created successfully")
            
            # if sow_data.get("PartnerUUID") is not None:
            #     folder_data = FolderManager(self.db, self.token_info, self.Company_Portal_Url)
            #     folderId = folder_data.get_folder_by_uuid(sow_data["PartnerUUID"])[0]["ID"]
            #     folder_data.create_folder(
            #         data = FolderSchema(
            #             FolderName=sow_data["SOWName"],
            #             ParentFolderID=folderId,
            #             EntityType="SOW"
            #         )
            #     )
            #     logging.info("Folder created successfully")
            
            return JSONResponse(
                status_code=201,
                content={"message": "SOW created successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during SOW creation: {str(e)}")
            raise e

    def get_project_info(self, project_name: int):
        try:
            query = text(f'''
                SELECT "ProjectUUID", "ProjectName"
                FROM {self.project_table}
                WHERE "ID" = :ProjectName
            ''')
            result = self.db.execute(query, {"ProjectName": project_name}).mappings().one()
            if result is None:
                return error.error("Project not found", 404, "Project Info")
            return result
        except Exception as e:
            logger.error(f"Error fetching project info: {str(e)}")
            raise e

    def get_client_info(self, client_name: int):
        try:
            query = text(f'''
                SELECT "ClientUUID", "ClientName"
                FROM {self.client_table}
                WHERE "ID" = :ClientName
            ''')
            result = self.db.execute(query, {"ClientName": client_name}).mappings().one()
            if result is None:
                return error.error("Client not found", 404, "Client Info")
            return result
        except Exception as e:
            logger.error(f"Error fetching client info: {str(e)}")
            raise e
    
    def get_vendor_info(self, vendor_name: int):
        try:
            query = text(f'''
                SELECT "VendorUUID", "VendorName"
                FROM {self.vendor_table}
                WHERE "ID" = :VendorName
            ''')
            result = self.db.execute(query, {"VendorName": vendor_name}).mappings().one()
            if result is None:
                return error.error("Vendor not found", 404, "Vendor Info")
            return result
        except Exception as e:
            logger.error(f"Error fetching vendor info: {str(e)}")
            raise e
    
    def get_user_info(self, user_id: int):
        try:
            query = text(f'''
                SELECT "UserUUID"
                FROM {self.user_table}
                WHERE "ID" = :user_id
            ''')
            result = self.db.execute(query, {"user_id": user_id}).mappings().one()
            if result is None:
                return error.error("Client not found", 404, "Client Info")
            return result
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            raise e

    def update_sow(self, sow_id: int, sowdata: SOWSchema):
        try:
            print("\n sowID", sow_id, "\n sowdata", sowdata)
            existing_sow = self._get_sow(sow_id)

            if not existing_sow:
                return error.error("SOW not found", 404, "SOW Info")
                
            
            if isinstance(sowdata, SOWSchema):
                sow_data = sowdata.dict()
                sow_data.pop("Company_Portal_Url", None)
            else:
                sow_data = {k: v for k, v in sowdata.items() if v is not None}
                
            sow_data["ID"] = sow_id
            sow_data["UpdatedTimeAndDate"] = datetime.now()
            print("\n sow_dataa:", sow_data, "\n")
            
            if sow_data["ProjectID"] is not None:
                project_info = self.get_project_info(sow_data.get("ProjectID"))
                sow_data["ProjectUUID"] = project_info["ProjectUUID"]
                sow_data["ProjectName"] = project_info["ProjectName"]
            sow_data.pop("ProjectID", None)
            
            if sow_data["ClientID"] is not None:
                client_info = self.get_client_info(sow_data.get("ClientID"))
                sow_data["ClientUUID"] = client_info["ClientUUID"]
                sow_data["ClientName"] = client_info["ClientName"]
            sow_data.pop("ClientID", None)
            
            if sow_data["ClientRepresentive"] is not None:
                user_info = self.get_user_info(sow_data.get("ClientRepresentive"))
                sow_data["ClientRepresentive"] = user_info["UserUUID"]

            filtered_sow_data = {key: value for key, value in sow_data.items() if value is not None}

            # Generate the update fields string, excluding the "ID" key
            update_fields = ", ".join(
                [f'"{key}" = :{key}' for key in filtered_sow_data.keys() if key != "ID"]
            )

            update_query = text(f'''
                UPDATE {self.sow_table}
                SET {update_fields}
                WHERE "ID" = :ID
            ''')

            self.db.execute(update_query, sow_data)
            updated_name = sow_data.get("SOWName", "")  # The new client name to update
            existing_name = existing_sow[0]["SOWName"]
            self.update_restFields(updated_name, existing_name)
            self.db.commit()
            return {"message": "SOW updated successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during SOW update: {str(e)}")
            raise e

    def update_restFields(self, updated, existing):
        # Update clientName in other related tables
        print(updated, existing)
        related_tables = [self.timesheet_table, self.user_table]  # Add all related table names here
        for table in related_tables:
            if table == self.user_table:
                update_related_query = text(f'''
                    UPDATE {table}
                        SET "SOW" = (
                            SELECT jsonb_agg(
                                CASE 
                                    WHEN value = :existing THEN :updated
                                    ELSE value
                                END
                            )
                            FROM jsonb_array_elements_text("SOW") AS value
                        )
                        WHERE "SOW" @> jsonb_build_array(:existing)
                    ''')
            else:
                update_related_query = text(f'''
                    UPDATE {table}
                    SET "SOWName" = :updated
                    WHERE "SOWName" = :existing
                ''')
            try:
                self.db.execute(update_related_query, {"updated": updated, "existing": existing})
            except Exception as e:
                logger.error(f"Error updating table {table}: {e}")
                raise
            
    def get_sow(self, sow_id: int = None, ProjectID: int = None, ClientID: int = None, PartnerID:int = None, VendorID: int = None):
        try:
            if ProjectID is not None:
                project_info = self.get_project_info(ProjectID)
                print(project_info["ProjectUUID"])
                sow = self._get_sow(projectUUID = project_info["ProjectUUID"])
            elif ClientID is not None:
                client_info = self.get_client_info(ClientID)
                sow = self._get_sow(clientUUID = client_info["ClientUUID"])
            elif VendorID is not None:
                vendor_info = self.get_vendor_info(VendorID)
                print(vendor_info)
                sow = self._get_sow(vendorUUID = vendor_info["VendorUUID"])
            elif PartnerID is not None:
                from Models.Classes.PartnerManager import PartnerManager
                partner_info = PartnerManager(self.db, self.token_info, self.Company_Portal_Url).get_partner(PartnerID)[0]
                sow = self._get_sow(partnerUUID = partner_info["PartnerUUID"])
            else:
                sow = self._get_sow(sow_id)
            if not sow:
                return error.error("SOW not found", 404, "SOW Info")
            
            return sow
        except Exception as e:
            print("Error:", e)
            logger.error(
                f"An unexpected error occurred while fetching SOW: {str(e)}")
            raise e

    def delete_sow(self, sow_id: int):
        try:
            existing_sow = self._get_sow(sow_id)

            if not existing_sow:
                return error.error("SOW not found", 404, "SOW Info")

            delete_query = text(
                f'DELETE FROM {self.sow_table} WHERE "ID" = :SOWID')
            self.db.execute(delete_query, {"SOWID": sow_id})
            self.db.commit()

            return {"message": "SOW deleted successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error occurred: {str(e)}")
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during SOW deletion: {str(e)}")
            raise e