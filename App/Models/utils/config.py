import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_TITLE: str = os.getenv("PROJECT_TITLE")
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION")
    APP_PORT= int(os.getenv("APP_PORT"))
    HOST: str = os.getenv("HOST")
    
    UID: str = os.getenv("UID")
    POOL_SIZE=int(os.getenv("POOL_SIZE"))
    POOL_TIMEOUT=int(os.getenv("POOL_TIMEOUT"))
    DB_PASSWORD: str = os.getenv("DB_PASSWORD")
    DB: str = os.getenv("DB")
    PSQL_SERVER = os.getenv("PSQL_SERVER")
    POOL_RECYCLE= int(os.getenv("POOL_RECYCLE"))
    MAX_OVERFLOW = int(os.getenv("MAX_OVERFLOW"))
    
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY")
    EMAIL: str = os.getenv("EMAIL")
    
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    
    URL_DATABASE = f'postgresql://{UID}:{DB_PASSWORD}@{PSQL_SERVER}/{DB}'
    print(URL_DATABASE)
    
    S3_REGION: str = os.getenv("S3_REGION")
    S3_URL: str = os.getenv("S3_URL")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY")
    S3_PRIVATE_KEY: str = os.getenv("S3_PRIVATE_KEY")
    
settings = Settings()