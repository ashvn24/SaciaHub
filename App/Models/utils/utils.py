from fastapi import HTTPException, status


class utils:
    def __init__(self):
        pass
    
    @staticmethod
    def is_admin(token_info):
        if not token_info["role"] in ["Admin", "Manager", "HR"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You do not have the permission to perform this action"
            )
    
    @staticmethod
    def error_message(msg):
        return {
            "status_code": 400,
            "detail": msg
        }
        
    @staticmethod
    def success(msg):
        return {
            "status_code":200,
            "detail": msg
        }

util = utils()