import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from Models.utils.config import settings

engine = create_engine(
    settings.URL_DATABASE,
    pool_size=settings.POOL_SIZE,           
    max_overflow=settings.MAX_OVERFLOW,         
    pool_timeout=settings.POOL_TIMEOUT,        
    pool_recycle=settings.POOL_RECYCLE     
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
