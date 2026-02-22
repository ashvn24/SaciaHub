"""Violation schemas."""

from typing import Optional

from pydantic import BaseModel


class violationSchema(BaseModel):
    Company_Portal_Url: str
    Useruuid: str
    violationType: str
    description: Optional[str] = None
    attachment: Optional[str] = None
