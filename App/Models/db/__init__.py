from .db_connection import engine, Base
from .models import TenantInfo, User_bgv, User_Violation


Base.metadata.create_all(bind=engine)

print("working")

from .schemas import *
from .db_connection import get_db