from fastapi import APIRouter
from .userbgv import router as bgrouter
from .dashboard import router as dashroute

api_router = APIRouter()

api_router.include_router(bgrouter)
api_router.include_router(dashroute)