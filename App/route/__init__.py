from .adminManagement import api_router as adminroute
from .HRmanagement import api_router as hrroute

from fastapi import APIRouter

apiroute = APIRouter()

apiroute.include_router(adminroute)
apiroute.include_router(hrroute)