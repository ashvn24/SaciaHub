import asyncio
from sqlalchemy import text
from sqlalchemy.orm import Session
from route.Notification.channels import manager
from datetime import datetime, timedelta
from uuid import UUID
import json
from Models.utils.error_handler import ErrorHandler

error = ErrorHandler()


class ManageNotification:

    def __init__(self, db: Session, customer):
        self.db = db
        self.shortname = customer.ShortName
        self.schema = customer.SchemaName
        self.manager = manager
        self.notification_table = f"{self.schema}.tb_{
            self.shortname}_notification"
        self.tenant_settings_table = f"{self.schema}.tb_{
            self.shortname}_tenant_settings"

    def _get_user_details(self, Id):
        user_table_name = f"{self.schema}.tb_{self.shortname}_user_info"
        select_query = text(
            f'SELECT "FirstName" FROM {user_table_name} WHERE "UserUUID" = :ID'
        )
        result = self.db.execute(select_query, {"ID": Id})
        return result.mappings().one()

    def create_notification(self, type, action, to_uuid, from_uuid, date, retype=None):
        if type == 'Timesheet':

            if action == "Approve":
                message = f"TimeSheet Approved"
            elif action == "Deny":
                message = f"TimeSheet Denied"
            elif action == "Created":
                name = self._get_user_details(Id=from_uuid)
                message = f"New Timesheet Created by {name.get('FirstName')}"
            else:
                raise ValueError("Invalid action for timesheet notification")
            data = {
                "message": message,
                "type": type,
            }

        elif type == 'Request':

            if action == "Approve":
                if retype == "Access":
                    message = f"Hardware Access granded"
                elif retype == "HR":
                    message = f"HR Request Approved"
                elif retype == "TimeOff":
                    message = f"TimeOff Request Approved"
                elif retype == "ProfileChange":
                    message = f"Profile Updated"
                else:
                    retype == "TimeSheet"
                    message = f"Missed TimeSheet Approved"
            elif action == "Deny":
                if retype == "Access":
                    message = f"Hardware Access Denied"
                elif retype == "HR":
                    message = f"HR Request Denied"
                elif retype == "TimeOff":
                    message = f"TimeOff Request Denied"
                elif retype == "ProfileChange":
                    message = f"Profile Update Denied"
                else:
                    retype == "TimeSheet"
                    message = f"Missed TimeSheet Denied"
            elif action == "Created":
                name = self._get_user_details(Id=from_uuid)
                message = f"New {retype} Request Created by {
                    name.get('FirstName')}"
            else:
                raise ValueError("Invalid action for request notification")
            data = {
                "message": message,
                "type": "Missed TimeSheet" if retype == "TimeSheet" else retype,
            }

        inserted_row = self.create_notifications(
            to_uuid, from_uuid, message, type, sub=retype)
        print("inserted_row:", inserted_row)
        asyncio.create_task(
            self.manager.send_personal_message(message=self.serialize_notification_row(inserted_row), user_uuid=to_uuid))

    def create_notifications(self, to_uuid, from_uuid, message, type, sub=None):
        insert_query = text(f"""
                INSERT INTO {self.notification_table}
                ("ToUUID", "FromUUID", "Notification_Type","Notification_SubType",
                 "Notification_Message", "Notification_Read")
                VALUES (:to_uuid, :from_uuid, :notification_type, :type, :message, FALSE)
                RETURNING *
            """)

        result = self.db.execute(insert_query, {
            "to_uuid": to_uuid,
            "from_uuid": from_uuid,
            "notification_type": type,
            "message": message,
            "type": sub
        })

        self.db.commit()
        return result.mappings().first()
    

    def serialize_notification_row(self, row):
        res = {
            k: (
                str(v) if isinstance(v, (UUID, datetime)) 
                else v
            )
            for k, v in row.items()
        }
        print("------------------------Serialized Row:--------------------------\n", json.dumps(res))
        return json.dumps(res)

    async def get_notification(self, token_info):
        one_month_ago = datetime.now() - timedelta(days=30)
        select_query = text(f"""
            SELECT * FROM {self.notification_table}
            WHERE "ToUUID" = :ToUUID
            AND "Created_date" >= :one_month_ago
            ORDER BY "Created_date" DESC
            """)
        notifications = self.db.execute(
            select_query, {"ToUUID": token_info['Id'], "one_month_ago": one_month_ago})
        return notifications.mappings().all()
    

    async def update_notification(self, notification_ids: list, read: bool):
        if not notification_ids:
            return

        update_query = text(f"""
            UPDATE {self.notification_table}
            SET "Notification_Read" = :read
            WHERE "ID" = ANY(:ids)
        """)

        self.db.execute(update_query, {
            "read": read,
            "ids": notification_ids
        })
        self.db.commit()