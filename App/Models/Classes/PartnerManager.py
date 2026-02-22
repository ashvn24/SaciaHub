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
from Models.db import models
from Models.db.schemas import FolderSchema, PartnerSchema
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)


class PartnerManager:
    def __init__(self, db: Session, token_info, Company_portal_Url):
        self.db = db
        self.token_info = token_info
        self.Company_portal_Url = Company_portal_Url
        self.customer = self.get_tenant_info(Company_portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.is_admin = self._is_admin(token_info)
        self.setup_tables()
        GetUser(self.db, Company_portal_Url).verify_user(token_info)
    
    def setup_tables(self):
        self.partner_table = f"{self.schema_name}.tb_{self.short_name}_partner_info"
        self.tenant_table = f"{self.schema_name}.tb_{self.short_name}_tenant_info"
        
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
        if "role" not in token_info or token_info["role"] not in ["Admin", "Manager"]:
            return error.error("Admin privileges required", 403, "Admin Privileges Required")
        return True
    
    def create_partner(self, data: PartnerSchema):
        try:
            partner_data = data.dict()
            partner_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_portal_Url)

            # Handle empty fields and arrays
            partner_data['PartnerUUID'] = str(uuid4())
            partner_data['CreatedBy'] = self.token_info['Id']
            partner_data["TenantUUID"] = tenant.TenantUUID
            partner_data["UpdatedTimeAndDate"] = None
            
            # Convert empty strings to None for array fields
            if 'logo_url' in partner_data and partner_data['logo_url'] == '':
                partner_data['logo_url'] = None

            # Convert empty arrays to proper PostgreSQL array format
            for key in partner_data:
                if isinstance(partner_data[key], list):
                    if not partner_data[key]:
                        partner_data[key] = '{}'  # Empty PostgreSQL array
                    else:
                        partner_data[key] = '{' + ','.join(str(x) for x in partner_data[key]) + '}'
            
            columns = ", ".join([f'"{k}"' for k in partner_data.keys()])
            values = ", ".join([f':{k}' for k in partner_data.keys()])
            
            insert_query = text(f'INSERT INTO {self.partner_table} ({columns}) VALUES ({values})')
            
            self.db.execute(insert_query, partner_data)
            self.db.commit()

            # Create folder for partner
            data = FolderSchema(
                FolderName=partner_data['PartnerName'],
                ParentFolderID=None,
                EntityType="Partner"
            )
            FolderManager(self.db, self.token_info, self.Company_portal_Url).create_folder(data, partner_data['PartnerUUID'])
            
            return JSONResponse(
                status_code=status.HTTP_201_CREATED, 
                content={"message": "Partner created successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error while creating partner: {e}")
            raise e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error: {e}")
            raise e
    
    def get_partner(self, partner_id: int = None):
        dynamic_query = text(f'SELECT * FROM {self.partner_table}')
        if partner_id is not None:
            dynamic_query = text(f'{dynamic_query} WHERE "ID" = :PartnerID')
        return self.db.execute(dynamic_query, {"PartnerID": partner_id}).mappings().all()

    def update_partner(self, partner_id: int, data: PartnerSchema):
        try:
            partner_data = data.dict()
            partner_data['UpdatedTimeAndDate'] = datetime.now()
            partner_data.pop("Company_Portal_Url", None)

            # Handle empty fields and arrays
            if 'logo_url' in partner_data and partner_data['logo_url'] == '':
                partner_data['logo_url'] = None

            # Convert empty arrays to proper PostgreSQL array format
            for key in partner_data:
                if isinstance(partner_data[key], list):
                    if not partner_data[key]:
                        partner_data[key] = '{}'  # Empty PostgreSQL array
                    else:
                        partner_data[key] = '{' + ','.join(str(x) for x in partner_data[key]) + '}'

            # Create the SET clause for the UPDATE statement
            set_clause = ", ".join([f'"{k}" = :{k}' for k in partner_data.keys()])
            
            update_query = text(f'UPDATE {self.partner_table} SET {set_clause} WHERE "ID" = :PartnerID')
            
            self.db.execute(update_query, {**partner_data, "PartnerID": partner_id})
            self.db.commit()
            
            return JSONResponse(
                status_code=200, 
                content={"message": "Partner updated successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error while updating partner: {e}")
            raise e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error: {e}")
            raise e
        
    def delete_partner(self, partner_id: int):
        try:
            delete_query = text(f'DELETE FROM {self.partner_table} WHERE "ID" = :PartnerID')
            self.db.execute(delete_query, {"PartnerID": partner_id})
            self.db.commit()
            return JSONResponse(status_code=200, content={"message": "Partner deleted successfully"})
        except SQLAlchemyError as e:
            logger.error(f"Error while deleting partner: {e}")
            raise e