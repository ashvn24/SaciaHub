import json
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from typing import Dict, List
import logging
from uuid import uuid4
from App.Models.Classes.GetUser import GetUser
from App.Models.Classes.folderManager import FolderManager
from Models.db.schemas import ClientSchema, FolderSchema, TimpolicySchema
from Models.db import models
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()

logger = logging.getLogger(__name__)


class ClientManager:
    def __init__(self, db: Session, token_info, Company_portal_Url):
        self.db = db
        self.token_info = token_info
        self.customer = self.get_tenant_info(Company_portal_Url)
        self.schema_name = self.customer.SchemaName
        self.short_name = self.customer.ShortName
        self.is_admin = self._is_admin(token_info)
        self.setup_client_table()
        GetUser(db, Company_portal_Url).verify_user(token_info)

    def _get_client_table_name(self):
        return f"{self.schema_name}.tb_{self.short_name}_client_info"

    def setup_client_table(self):
        self.client_table = f"{self.schema_name}.tb_{
            self.short_name}_client_info"
        self.tenant_table = f"{self.schema_name}.tb_{
            self.short_name}_tenant_info"
        self.project_table = f"{self.schema_name}.tb_{
            self.short_name}_project_info"
        self.sow_table = f"{self.schema_name}.tb_{
            self.short_name}_sow_info"
        self.user_table = f"{self.schema_name}.tb_{
            self.short_name}_user_info"
        self.timesheetPolicytable = f"{self.schema_name}.tb_{
            self.short_name}_timesheet_policy"
        self.timesheet_table = f"{self.schema_name}.tb_{
            self.short_name}_timesheet"
        self.folder_table = f"{self.schema_name}.tb_{
            self.short_name}_folders"

    def _get_client(self, client_id: int = None, clientuuid: str = None):
        dynamic_query = text(f'SELECT * FROM {self.client_table}')
        params = {} 
        
        if client_id is not None:
            dynamic_query = f'{dynamic_query} WHERE "ID" = :ClientID'
            params["ClientID"] = client_id
            
        if clientuuid is not None:
            dynamic_query = f'{dynamic_query} WHERE "ClientUUID" = :ClientUUID'
            params["ClientUUID"] = clientuuid
            
        return self.db.execute(text(f'{dynamic_query} ORDER BY "ID" DESC'), params).mappings().all()

    def get_tenant_(self, company_portal_url: str):
        select_query = text(
            f'SELECT * FROM {self.tenant_table} WHERE "PortalURL" = :PortalURL')
        return self.db.execute(select_query, {"PortalURL": company_portal_url}).mappings().one()

    def _is_admin(self, token_info):
        if "role" not in token_info or token_info["role"] not in ["Admin", "Manager", "HR", "user"]:
            return error.error("Unauthorized access", 403, "Unauthorized access")
        return True

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

    def create_client(self, data: ClientSchema):
        try:
            client_data = data.dict()
            client_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_Portal_Url)
            # Add UUID fields
            client_data["ClientID"] = str(uuid4())[:8]
            client_data["ClientUUID"] = str(uuid4())
            client_data["TenantUUID"] = tenant.TenantUUID
            client_data["UpdatedTimeAndDate"] = None
            client_data["CreatedBy"] = self.token_info['Id']
            columns = ", ".join([f'"{k}"' for k in client_data.keys()])
            values = ", ".join([f":{k}" for k in client_data.keys()])

            insert_query = text(f'''
                INSERT INTO {self.client_table} ({columns})
                VALUES ({values})
            ''')

            self.db.execute(insert_query, client_data)
            self.db.commit()
            FolderManager(self.db, self.token_info, self.Company_Portal_Url).create_folder(
                data=FolderSchema(
                    FolderName=client_data["ClientName"], 
                    ParentFolderID=None, 
                    EntityType="Client",
                ), 
                clientuuid=client_data["ClientUUID"]
            )
            
            return JSONResponse(
                status_code=201,
                content={"message": "Client created successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
        except Exception as ee:
            raise ee

    def update_client(self, client_id: int, clientdata: ClientSchema):
        try:
            existing_client = self._get_client(client_id)
            client_data = clientdata.dict()
            client_data.pop("Company_Portal_Url", None)
            client_data["ClientID"] = client_id
            if not existing_client:
                return error.error("Client not found", 404, "Client Not Found")

            update_fields = ", ".join(
                [f'"{key}" = :{key}' for key in client_data.keys() if key != "ID"])

            update_query = text(f'''
                UPDATE {self.client_table}
                SET {update_fields}
                WHERE "ID" = :ClientID
            ''')

            self.db.execute(
                update_query, client_data)
            updated_name = client_data.get("ClientName", "")  # The new client name to update
            existing_name = existing_client[0]["ClientName"]
            # print("\n client:",client_data['ClientName'], "\n\n exis:", existing_client)
            self.update_relatedFields(updated_name, existing_name)

            self.db.commit()
            return JSONResponse(
                status_code=200,
                content={"message": "Client updated successfully"}
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
        except Exception as ee:
            raise ee
            
    def update_relatedFields(self, updated, existing):
        # Update clientName in other related tables
        print(updated, existing)
        related_tables = [self.project_table, self.sow_table, self.timesheet_table, self.user_table]  # Add all related table names here
        for table in related_tables:
            if table == self.user_table:
                update_related_query = text(f'''
                    UPDATE {table}
                        SET "Client" = (
                            SELECT jsonb_agg(
                                CASE 
                                    WHEN value = :existing THEN :updated
                                    ELSE value
                                END
                            )
                            FROM jsonb_array_elements_text("Client") AS value
                        )
                        WHERE "Client" @> jsonb_build_array(:existing)
                    ''')
            else:
                update_related_query = text(f'''
                    UPDATE {table}
                    SET "ClientName" = :updated
                    WHERE "ClientName" = :existing
                ''')
            try:
                self.db.execute(update_related_query, {"updated": updated, "existing": existing})
            except Exception as e:
                raise e
    def get_client(self, client_id: int = None):
        try:
            client = self._get_client(client_id)
            if not client:
                return error.error("Client not found", 404, "Client Not Found")
            return client
        except Exception as ee:
            raise ee

    def delete_client(self, client_id: int):
        try:
            existing_client = self._get_client(client_id)

            if not existing_client:
                return error.error("Client not found", 404, "Client Not Found")

            delete_query = text(
                f'DELETE FROM {self.client_table} WHERE "ID" = :ClientID')
            self.db.execute(delete_query, {"ClientID": client_id})
            self.delete_folders(existing_client[0])
            self.db.commit()

            return {"message": "Client deleted successfully"}

        except SQLAlchemyError as e:
            self.db.rollback()
            raise e
        except Exception as ee:
            raise ee
            
    def delete_folders(self, data):
        
        deleteFolderquery = text(
            f'DELETE FROM {self.folder_table} WHERE "EntityUUID" = :uuid')
        self.db.execute(deleteFolderquery, {"uuid": data["ClientUUID"]})
    
    def assign_clients(self, User_id, client_id):
        try:
            client = self._get_client(client_id)[0]["ClientUUID"]
            print(client)
            if not client:
                return error.error("Client not found", 404, "Client Not Found")
            update_query = text(
                f'''
                UPDATE {self.user_table}
                SET "Client" = COALESCE("Client", '[]'::jsonb) || CAST(:client AS jsonb)
                WHERE "ID" = :User_id
                '''
            )
            self.db.execute(
                update_query, {"client": json.dumps([client]), "User_id": User_id}
            )
            self.db.commit()
            return JSONResponse(
                status_code=200,
                content={"message": "Client assigned successfully"}
            )
        except Exception as ee:
            raise ee
    
    def assign_client(self, User_id: int, client_ids: List[int], projectID: List[int]):
        try:
            # First, get the UserUUID of the user we're assigning
            user_query = text(f'SELECT "UserUUID" FROM {self.user_table} WHERE "ID" = :User_id')
            user_result = self.db.execute(user_query, {"User_id": User_id}).first()
            
            if not user_result:
                return error.error(f"User with ID {User_id} not found", 404, "User Not Found")
            
            user_uuid = str(user_result[0])
            
            # Remove user from previously assigned projects
            cleanup_query = text(f'''
                UPDATE {self.project_table}
                SET "UsersAssigned" = (
                    SELECT CASE 
                        WHEN json_agg(value) IS NULL THEN '[]'::json
                        ELSE json_agg(value)
                    END
                    FROM jsonb_array_elements_text("UsersAssigned"::jsonb) 
                    WHERE value != :user_uuid
                )
                WHERE "UsersAssigned"::jsonb ? :user_uuid
            ''')
            self.db.execute(cleanup_query, {"user_uuid": user_uuid})
            
            clients = set()
            all_projects = set()
            all_sows = set()
            
            for client_id in client_ids:
                client = self._get_client(client_id)[0]["ClientUUID"]
                if not client:
                    return error.error(f"Client with ID {client_id} not found", 404, "Client Not Found")
                
                select_query = text(
                    f'''
                    SELECT p."ClientUUID", p."ProjectUUID", p."ID",
                    p."ProjectTimesheetBuckets", ps."SOWUUID", p."UsersAssigned"
                    FROM {self.project_table} p
                    JOIN {self.sow_table} ps ON p."ProjectUUID" = ps."ProjectUUID"
                    WHERE p."ClientUUID" = :ClientUUID AND p."ID" = ANY(:project_ids)
                    '''
                )
                
                result = self.db.execute(
                    select_query, 
                    {
                        "ClientUUID": client,
                        "project_ids": projectID
                    }
                ).mappings().all()
                
                if result:
                    for r in result:
                        clients.add(r["ClientUUID"])
                        all_projects.add(r["ProjectUUID"])
                        all_sows.add(r["SOWUUID"])
                        
                        # Update UsersAssigned for each project
                        project_id = r["ID"]
                        try:
                            current_users = r["UsersAssigned"] if r["UsersAssigned"] else []
                        except Exception as e:
                            print(f"Error parsing UsersAssigned: {e}")
                            current_users = []
                        if user_uuid not in current_users:
                            current_users.append(user_uuid)
                            users_json = json.dumps(current_users)
                            
                            update_project_query = text(f'''
                                UPDATE {self.project_table}
                                SET "UsersAssigned" = cast(:users as json)
                                WHERE "ID" = :project_id
                            ''')
                            
                            self.db.execute(
                                update_project_query, {
                                    "users": users_json,
                                    "project_id": project_id
                                }
                            )

            if clients:
                # Convert sets to lists and then to JSON strings
                clients_json = json.dumps([str(client) for client in clients])
                projects_json = json.dumps([str(project) for project in all_projects])
                sows_json = json.dumps([str(sow) for sow in all_sows])
                
                update_query = text(f'''
                    UPDATE {self.user_table}
                    SET 
                        "Client" = cast(:client as json),
                        "Project" = cast(:project as json),
                        "SOW" = cast(:sow as json)
                    WHERE "ID" = :User_id
                ''')

                self.db.execute(
                    update_query, {
                        "client": clients_json,
                        "project": projects_json,
                        "sow": sows_json,
                        "User_id": User_id
                    }
                )
                self.db.commit()
                return {
                    "status": "success",
                    "message": f"User {User_id} assigned to clients successfully",
                    "assigned_clients": list(clients),
                    "assigned_projects": list(all_projects),
                    "assigned_sows": list(all_sows)
                }
                
            return JSONResponse(
                status_code=200,
                content={"message": "Clients assigned successfully"}
            )
        except Exception as e:
            raise e
            
    async def createTimesheetPolicy(self, data:TimpolicySchema):
        try:
            client_data = data.dict()
            client_data.pop("Company_Portal_Url", None)
            tenant = self.get_tenant_(self.Company_Portal_Url)
            
            client_data["TenantUUID"] = tenant.TenantUUID
            client_data["Timesheet_fields"] = json.dumps({
                "Fields": client_data["Timesheet_fields"]
            })
            
            columns = ", ".join([f'"{k}"' for k in client_data.keys()])
            values = ", ".join([f":{k}" for k in client_data.keys()])
            
            print("\n clientdata",client_data)
            print("\n columns:", columns, "\n values:", values)
            insert_query = text(f'''
                    INSERT INTO {self.timesheetPolicytable} ({columns})
                    VALUES ({values})
                ''')

            self.db.execute(insert_query, client_data)
            self.db.commit()
            
            return JSONResponse(
                status_code=201,
                content={"message": "TIM policy created successfully"}
            )
        
        except SQLAlchemyError as sql_exc:
            self.db.rollback()
            raise sql_exc
        except Exception as e:
            raise e