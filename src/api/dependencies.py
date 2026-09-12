from fastapi import Request, Depends, HTTPException, Cookie
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import AppError, ErrorCode
from src.core.response import error_response
from src.models.user import User, AuthStatus
from src.services.auth_service import AuthService
from src.adapters.email_adapter import get_email_adapter


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Получение сервиса авторизации"""
    return AuthService(db, get_email_adapter())


async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    session_cookie: Optional[str] = Cookie(None, alias="session_id"),
) -> User:
    """
    Получение текущего пользователя из session cookie.
    Раздел 3.2 ТЗ - cookie-session flow.
    """
    # Пробуем получить токен из cookie или из заголовка Authorization
    session_token = session_cookie
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail=error_response(
                code=ErrorCode.AUTH_REQUIRED,
                message="Требуется авторизация",
                request_id=request.state.request_id,
            )
        )
    
    result = await auth_service.get_session(session_token)
    if not result:
        raise HTTPException(
            status_code=401,
            detail=error_response(
                code=ErrorCode.TOKEN_EXPIRED,
                message="Сессия истекла. Войдите заново.",
                request_id=request.state.request_id,
            )
        )
    
    user, session = result
    
    # Проверка статуса пользователя
    if user.auth_status == AuthStatus.DELETION_PENDING:
        raise HTTPException(
            status_code=403,
            detail=error_response(
                code=ErrorCode.ACCESS_DENIED,
                message="Аккаунт в процессе удаления",
                request_id=request.state.request_id,
            )
        )
    
    # Сохраняем сессию в request для CSRF проверки
    request.state.session = session
    
    return user
