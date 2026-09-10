import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt, JWTError

from src.core.config import settings

# Контекст для хеширования паролей (раздел 11 ТЗ - modern adaptive hash)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_token(length: int = 32) -> str:
    """Генерация случайного токена"""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    Хеширование токена для хранения в БД (раздел 11 ТЗ).
    Токены храним hashed и делаем одноразовыми.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT access token (если выбран token flow)"""
    if expires_delta is None:
        expires_delta = timedelta(seconds=settings.SESSION_MAX_AGE)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """Декодирование JWT"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None