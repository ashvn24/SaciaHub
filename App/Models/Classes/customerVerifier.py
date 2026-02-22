from sqlalchemy.sql import text
from fastapi import status
from fastapi.responses import JSONResponse
from Models.db import models
from sqlalchemy.orm import Session


class CustomerUserVerifier:
    def __init__(self, db: Session):
        self.db = db

    def verify_customer_and_user(self, company_portal_url, user_id):
        customer = self._get_customer(company_portal_url)
        if not customer:
            return self._create_error_response(
                "Customer not found", status.HTTP_404_NOT_FOUND
            )

        user = self._get_user(customer, user_id)
        if not user:
            return self._create_error_response(
                "User not found", status.HTTP_404_NOT_FOUND
            )

        return customer, user

    def _get_customer(self, company_portal_url):
        return (
            self.db.query(models.TenantInfo)
            .filter(models.TenantInfo.PortalURL == company_portal_url)
            .first()
        )

    def _get_user(self, customer, user_id):
        user_table_name = f"{customer.SchemaName}.tb_{
            customer.ShortName}_user_info"
        dynamic_query_email = text(
            f'SELECT * FROM {user_table_name} WHERE "UserUUID" = :ID'
        )
        return self.db.execute(dynamic_query_email, {"ID": user_id}).fetchone()

    @staticmethod
    def _create_error_response(message, status_code):
        return JSONResponse(
            status_code=status_code,
            content={"message": message},
        )
