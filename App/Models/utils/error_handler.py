from fastapi import HTTPException
from datetime import datetime, timezone


class ErrorHandler:
    def error(self, msg: str, status: int, err_type: str):
        data = {
            "err_msg": msg,
            "status": status,
            "time": datetime.now(timezone.utc).isoformat(),
            "type": err_type
        }
        raise HTTPException(detail=data, status_code=status)
