from fastapi import APIRouter
from .adminroute import admin_router
from .bgvmanager import router as bgrouter
from .usermanage import router as usrouter
from .violation import router as violationroute
from .timesheet import router as tmrouter
from .dashboard import router as dashrouter

api_router = APIRouter()

api_router.include_router(admin_router)
api_router.include_router(bgrouter)
api_router.include_router(usrouter)
api_router.include_router(violationroute)
api_router.include_router(tmrouter)
api_router.include_router(dashrouter)