from typing import Optional
import uuid
import warnings

from fastapi import HTTPException, Header, status
from pytz import utc
from Models.db.db_connection import SessionLocal, engine
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os
from jose import jwt, JWTError
import random
import string
import os
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import base64
from Models.utils.error_handler import ErrorHandler
error = ErrorHandler()

load_dotenv()

ENCRYPTION_KEY = base64.b64decode(os.getenv("ENCRYPTION_KEY"))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
REFRESH_TOKEN_EXPIRE_DAYS = 2

Session = SessionLocal(bind=engine)
warnings.filterwarnings("ignore", category=UserWarning,
                        module="passlib.handlers.bcrypt")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

blacklisted_token = set()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(utc) + expires_delta
    else:
        expire = datetime.now(utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(utc) + expires_delta
    else:
        expire = datetime.now(utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(authorization: Optional[str] = Header(None)):

    if not authorization:
        raise error.error("Authorization header missing", 401, "Unauthorized")

    try:
        payload = jwt.decode(authorization, SECRET_KEY, algorithms=[ALGORITHM])
        # Convert 'exp' to UTC-aware datetime
        exp_timestamp = payload.get("exp", 0)
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Compare offset-aware datetime objects
        if datetime.now(timezone.utc) > exp_datetime:
            raise error.error("Token has expired", 401, "Unauthorized")

        token_id = payload.get("jti")
        if token_id and token_id in blacklisted_token:
            raise error.error("Token has been revoked", 401, "Unauthorized")

        return payload

    except JWTError:
        raise error.error("Session expired", 401, "Unauthorized")

def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


def encrypt_data(data: str) -> str:
    """Encrypt data using AES-CBC"""
    data_str = str(data)
    data_bytes = data_str.encode('utf-8')
    iv = get_random_bytes(16)
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
    encrypted_bytes = cipher.encrypt(pad(data_bytes, AES.block_size))

    encrypted_data = base64.b64encode(iv + encrypted_bytes).decode('utf-8')
    return encrypted_data

def decrypt_data(encrypted_data: str) -> str:
    # Decode the base64 string
    encrypted_bytes = base64.b64decode(encrypted_data)
    
    # Extract IV and ciphertext
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    
    # Create cipher object and decrypt the data
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
    decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
    
    # Convert decrypted bytes back to string
    decrypted_data = decrypted_bytes.decode('utf-8')
    return decrypted_data

async def validate_token(authorization: Optional[str] = Header(None)):
    if authorization is None:
        raise error.error("Authorization header missing", 401, "Unauthorized")
    token = authorization.split(
        " ")[1] if " " in authorization else authorization
    return decode_token(token)
