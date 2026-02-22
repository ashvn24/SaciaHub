from typing import List, Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import quoted_name, text
from Models.db import models
from Models.utils.error_handler import ErrorHandler
from typing import Optional
import json

error = ErrorHandler()


class GetUser:
    def __init__(self, db: Session, company_portal_url):
        self.db = db
        self.company_portal_url = company_portal_url
        self.tenant_info = self._get_tenant_info()
        self.user_table = f"{self.tenant_info.SchemaName}.tb_{self.tenant_info.ShortName}_user_info"
        self.project_table = f"{self.tenant_info.SchemaName}.tb_{self.tenant_info.ShortName}_project_info"
        
    def _get_tenant_info(self):
        user = (self.db.query(models.TenantInfo).filter(models.TenantInfo.PortalURL == self.company_portal_url).first())
        if user is None:
            return error.error("Schema not found", 404, "Schema Not Found")
        return user

    def get_user_uuids(self, user_ids: List[str]) -> List[str]:
        try:
            if not user_ids:
                return []
            query = text(f"""SELECT "UserUUID" FROM {self.user_table} WHERE "ID" IN :user_ids""")
            result = self.db.execute(query, {"user_ids": tuple(user_ids)})
            uuids = [row[0] for row in result]
            return uuids
        except Exception as e:
            print("error", e)

    def get_user_uuid_map(self, user_ids: List[str]) -> Dict[str, str]:
        if not user_ids:
            return {}
        query = text(f"""SELECT "ID", "UserUUID" FROM {self.user_table} WHERE "ID" IN :user_ids""")
        result = self.db.execute(query, {"user_ids": tuple(user_ids)})
        uuid_map = {str(row[0]): row[1] for row in result}
        return uuid_map

    def _verify_admin(self, role: str):
        if role not in ["Admin", "Manager", "ClientRep", "HR"]:
            return error.error("You do not have the permission to perform this action", 401, "Unauthorized")
    def verify_user(self, token_info: dict):
        query = text(f"""SELECT "UserUUID" FROM {self.user_table} WHERE "UserUUID" = :user_id""")
        result = self.db.execute(query, {"user_id": token_info["Id"]}).first()
        if not result:
            return error.error("Access denied", 404, "Access Denied")
            
    def get_userdetails_by_uuid(self, user_uuid: str):
        query = text(f"""SELECT * FROM {self.user_table} WHERE "UserUUID" = :user_uuid""")
        result = self.db.execute(query, {"user_uuid": user_uuid}).mappings().one_or_none()
        return result
    
    def get_all_users(self, token_info: dict, user_id: int = None, sortby: str =None,pagenum: int = None, own: int = None, sortBy: Optional[str] = None, order: Optional[int] = 1, filterBy: Optional[str] = None):
        self._verify_admin(token_info["role"])
        schema = quoted_name(self.tenant_info.SchemaName, True)
        user_table = quoted_name(f"{schema}.tb_{self.tenant_info.ShortName}_user_info", True)
        params = {}

        if filterBy:
            filterBy = json.loads(filterBy)
        else:
            filterBy = {}

        filters = []
        filters.append(f"u.\"UserUUID\" != '{token_info['Id']}'")
        if token_info["role"] == "Manager":
            filters.append(f"u.\"User_manager\" = '{token_info["Id"]}'")
        if token_info["role"] == "HR":
            filters.append(f"u.\"HR_Manager\" = '{token_info["Id"]}'")
        if user_id and user_id != token_info['Id']:
            filters.append("u.\"ID\" = :user_id")
        
        if filterBy:
            name = filterBy.get("name", "").strip()
            if name:
                filters.append('(LOWER(u."FirstName" || \' \' || u."LastName") ILIKE :full_name)')
                params["full_name"] = f"%{name.lower()}%"

            status = filterBy.get("status", "").strip()
            if status:
                filters.append('LOWER(u."Status") ILIKE :status')
                params["status"] = f"%{status.lower()}%"

            clients = filterBy.get("clients", "").strip()
            if clients:
                filters.append('EXISTS (SELECT 1 FROM user_projects up_sub WHERE up_sub.user_uuid = u."UserUUID" AND CAST(up_sub.project_client AS TEXT) ILIKE :clients)')
                params["clients"] = f"%{clients.lower()}%"
            
        role_filter = " AND ".join(filters) if filters else "1=1"

        # Valid sort columns mapping
        sort_column_map = {
            "username": "u.\"Username\"",
            "email": "u.\"Email\"",
            "role": "u.\"Role\"",
            "holidaypolicy": "hp.\"Template_Name\"",
            "timeoffpolicy": "tp.\"Timeoff_Policy_Name\"",
            "module": "u.\"Module\"",
            "client": "ARRAY_AGG(up.\"project_client\")",
            "status": "u.\"Status\""
        }

        order = "ASC" if order == 1 else "DESC"
        order_clause = ""
        if sortBy:
            sort_key = sortBy.lower()
            if sort_key in sort_column_map:
                order_clause = f"ORDER BY {sort_column_map[sort_key]} {order}"
            else:
                order_clause = ""
        else:
            order_clause = "ORDER BY u.\"ID\" ASC"

        query = text(f"""
            WITH user_projects AS (
                SELECT 
                    p."ID" AS project_id,
                    p."ProjectName",
                    c."ID" AS project_client,
                    (jsonb_array_elements_text(p."UsersAssigned"::jsonb))::uuid AS user_uuid
                FROM {schema}.tb_{self.tenant_info.ShortName}_project_info p
                JOIN {schema}.tb_{self.tenant_info.ShortName}_client_info c ON p."ClientUUID" = c."ClientUUID"
                WHERE p."UsersAssigned" IS NOT NULL 
                AND p."UsersAssigned"::jsonb != '[]'::jsonb
            )
            SELECT 
                u."ID", 
                u."Username", 
                u."FirstName", 
                u."LastName", 
                u."Role", 
                u."Email", 
                u."Module" AS "Module", 
                u."UserUUID", 
                u."User_manager",
                u."HR_Manager",
                u."Status",
                CONCAT(m."FirstName", ' ', m."LastName") AS "Manager_Name",
                m."ID" AS "ManagerID",
                CONCAT(hr."FirstName", ' ', hr."LastName") AS "HR_Manager_Name",
                hr."ID" AS "HR_ManagerID",
                u."UserTeam" AS "UserTeam", 
                u."JobTitle" AS "Job_Role",
                COALESCE(tp."Timeoff_Policy_Name", 'N/A') AS "Timeoff_Policy_Name", 
                tp."ID" AS "Timeoff_Policy_ID",
                COALESCE(hp."Template_Name", 'N/A') AS "Template_Name", 
                hp."Template_Country",
                hp."ID" AS "Holiday_Policy_ID",
                COALESCE(ARRAY_AGG(up."project_id") FILTER (WHERE up."project_id" IS NOT NULL), ARRAY[]::integer[]) AS "Projects",
                COALESCE(ARRAY_AGG(up."project_client") FILTER (WHERE up."project_client" IS NOT NULL), ARRAY[]::integer[]) AS "Client"
            FROM {schema}.tb_{self.tenant_info.ShortName}_user_info u
            LEFT JOIN {schema}.tb_{self.tenant_info.ShortName}_user_info m ON u."User_manager" = m."UserUUID"
            LEFT JOIN {schema}.tb_{self.tenant_info.ShortName}_user_info hr ON u."HR_Manager" = hr."UserUUID"
            LEFT JOIN {schema}.tb_{self.tenant_info.ShortName}_timeoff_policy tp ON u."Timeoff_Policy" = tp."ID"
            LEFT JOIN {schema}.tb_{self.tenant_info.ShortName}_holidaypolicy hp ON u."Holiday_Policy" = hp."ID"
            LEFT JOIN user_projects up ON u."UserUUID" = up.user_uuid
            WHERE {role_filter}
            GROUP BY 
                u."ID", 
                u."Username", 
                u."FirstName", 
                u."LastName", 
                u."Role", 
                u."Email", 
                u."Module"::text, 
                u."UserUUID", 
                u."User_manager",
                u."HR_Manager",
                m."FirstName",
                m."LastName",
                m."ID",
                hr."FirstName",
                hr."LastName",
                hr."ID",
                u."UserTeam"::text, 
                u."JobTitle",
                tp."Timeoff_Policy_Name",
                tp."ID",
                hp."Template_Country",
                hp."ID"
            {order_clause}
        """)


        
        if user_id:
            params["user_id"] = user_id

        result = self.db.execute(query, params).mappings().all()
        if pagenum is not None:
            if pagenum is None or pagenum == 0:
                pagenum = 1
            pageSize = 10
            totalitems = len(result)
            page_count = (totalitems // pageSize) + (1 if totalitems % pageSize > 0 else 0)
            result = None
            if result:
                if pagenum > 0 and pagenum <= page_count:
                    start_idx = (pagenum - 1) * pageSize
                    end_idx = start_idx + pageSize
                try:
                    result = result[start_idx:end_idx]
                except IndexError:
                    result = result[start_idx:]
            data = {}
            item = {"items": totalitems, "page": page_count}
            data["data"] = result
            data["total"] = item
            return data
        
        return result
    
    def delete_users(self, user_ids: List[int], token_info: dict):
        self._verify_admin(token_info["role"])
        print(user_ids)
        
        if not user_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user IDs provided"
            )
        if isinstance(user_ids, int):
            user_ids = [user_ids]
        elif not isinstance(user_ids, (list, tuple)):
            raise TypeError("user_ids must be a list, tuple, or single integer.")
        
        schema = quoted_name(self.tenant_info.SchemaName, True)
        user_table = quoted_name(f"{schema}.tb_{self.tenant_info.ShortName}_user_info", True)
        
        for uid in user_ids:
            print(uid)
            user_uuid = GetUser(self.db, self.company_portal_url).get_user_uuids([uid])
            print(user_uuid)
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
            self.db.execute(cleanup_query, {"user_uuid": str(user_uuid)})

        query = text(f"""DELETE FROM {user_table} WHERE "ID" IN :user_ids""")
        self.db.execute(query, {"user_ids": tuple(user_ids)})
        self.db.commit()
        return {"message": "Users deleted successfully"}

