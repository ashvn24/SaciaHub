from datetime import datetime
import json
from fastapi import HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from Models.db import models


class APILogger:
    def __init__(self, db: Session, Company_Portal_Url):
        self.db = db
        self.user = self.get_tenant_info(Company_Portal_Url)
        self.shortname = self.user.ShortName
        self.schema = self.user.SchemaName
        self.log_table = f'{self.schema}.tb_{self.shortname}_tenant_logs'

    def get_tenant_info(self, company_portal_url: str):
        user = (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )
        if user is None:
            raise HTTPException(status_code=404, detail="Schema not found")
        return user

    async def log_api_call(self, request: Request, response: Response, user_uuid: str, execution_time: float):
        query = text(f"""
            INSERT INTO {self.log_table} (
                "UserUUID", "TIMESTAMP", "HTTP_Method", "End_Point", "Request_Header", "Query_Parameters",
                "Request_Body", "Response_Status_Code", "Response_Body", "User_ID", "IP_Address",
                "Response_Time", "Error_Message", "Error_Code", "Auth_Token", "Permissions", "Session_ID",
                "Request_Origin", "Trace_ID", "CustomData"
            ) VALUES (
                :user_uuid, :timestamp, :http_method, :end_point, :request_header, :query_parameters,
                :request_body, :response_status_code, :response_body, :user_id, :ip_address,
                :response_time, :error_message, :error_code, :auth_token, :permissions, :session_id,
                :request_origin, :trace_id, :custom_data
            )
        """)
        print("here")
        # Get request body
        request_body = await request.body()
        print(request.state)
        status_code = getattr(request.state, 'status_code', 200)

        # Fetch permissions from token_info or fallback to Role from response
        permissions = None
        if hasattr(request.state, 'token_info') and request.state.token_info:
            permissions = json.dumps(request.state.token_info.get('role'))
        else:
            try:
                response_body = await response.body()  # Get response body as bytes
                response_body_decoded = response_body.decode(
                    'utf-8')  # Decode to string
                response_json = json.loads(
                    response_body_decoded)  # Convert to JSON
                permissions = json.dumps(response_json.get('Role'))
            except Exception as e:
                print(f"Error retrieving Role from response: {str(e)}")

        values = {
            "user_uuid": user_uuid,
            "timestamp": datetime.now(),
            "http_method": request.method,
            "end_point": request.url.path,
            "request_header": json.dumps(dict(request.headers)),
            "query_parameters": json.dumps(dict(request.query_params)),
            "request_body": request_body.decode(),
            "response_status_code": status_code,
            "response_body":  None,
            "user_id": request.headers.get("X-User-ID"),
            "ip_address": request.client.host,
            "response_time": execution_time,
            "error_message": None,
            "error_code": None,
            "auth_token": request.headers.get("Authorization"),
            "permissions": permissions,
            "session_id": request.headers.get("X-Session-ID"),
            "request_origin": request.headers.get("Origin"),
            "trace_id": request.headers.get("X-Trace-ID"),
            "custom_data": json.dumps({"company_portal_url": request.query_params.get("Company_Portal_Url")})
        }

        try:
            self.db.execute(query, values)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Error logging API call: {str(e)}")
