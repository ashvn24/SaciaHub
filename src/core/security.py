"""
Security utilities: JWT, password hashing, encryption.
"""

import base64
import random
import string
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.core.config import get_settings
from src.core.exceptions import (
    InvalidTokenException,
    TokenExpiredException,
    TokenRevokedException,
    UnauthorizedException,
)

warnings.filterwarnings("ignore", category=UserWarning, module="passlib.handlers.bcrypt")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory token blacklist (replace with Redis in production)
blacklisted_tokens: set = set()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_timestamp = payload.get("exp", 0)
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        if datetime.now(timezone.utc) > exp_datetime:
            raise TokenExpiredException()

        token_id = payload.get("jti")
        if token_id and token_id in blacklisted_tokens:
            raise TokenRevokedException()

        return payload
    except JWTError:
        raise InvalidTokenException()


def blacklist_token(token_id: str) -> None:
    """Add a token to the blacklist."""
    blacklisted_tokens.add(token_id)


def generate_random_password(length: int = 8) -> str:
    """Generate a random password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return "".join(random.choice(characters) for _ in range(length))


def encrypt_data(data: str) -> str:
    """Encrypt data using AES-CBC."""
    settings = get_settings()
    encryption_key = base64.b64decode(settings.ENCRYPTION_KEY)
    data_bytes = str(data).encode("utf-8")
    iv = get_random_bytes(16)
    cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
    encrypted_bytes = cipher.encrypt(pad(data_bytes, AES.block_size))
    return base64.b64encode(iv + encrypted_bytes).decode("utf-8")


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt AES-CBC encrypted data."""
    settings = get_settings()
    encryption_key = base64.b64decode(settings.ENCRYPTION_KEY)
    encrypted_bytes = base64.b64decode(encrypted_data)
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
    decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return decrypted_bytes.decode("utf-8")
