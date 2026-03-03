"""Notification schemas."""

from typing import List

from pydantic import BaseModel


class TenantNotificationSettings(BaseModel):
    timesheet_notification: bool
    request_notification: bool

    class Config:
        from_attributes = True


class UpdateNotification(BaseModel):
    notification_ids: List[int]
    read: bool
