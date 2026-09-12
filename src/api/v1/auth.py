from fastapi import APIRouter, Request, Depends, HTTPException, Response
from datetime import datetime, timezone

from src.core.config import settings
from src.core.response import success_response, error_response
from src.core.exceptions import AppError, ErrorCode
from src.schemas.auth import (
    RegisterRequest, LoginRequest, RestoreRequest,
    ResetPasswordRequest, VerifyEmailRequest, LogoutRequest
)
from src.services.auth_service import AuthService
from src.api.dependencies import get_auth_service, get_current_user
from src.models.user import User

router = APIRouter()


def handle_app_error(e: AppError, request: Request) -> HTTPException:
    """Преобразование AppError в HTTPException"""
    return HTTPException(
        status_code=e.status_code,
        detail=error_response(
            code=e.code,
            message=e.message,
            request_id=request.state.request_id,
            field_errors=e.field_errors,
            details=e.details,
            retryable=e.retryable
        )
    )


def set_session_cookie(response: Response, session_token: str) -> None:
    """Установка session cookie (раздел 11 ТЗ)"""
    response.set_cookie(
        key="session_id",
        value=session_token,
        max_age=settings.SESSION_MAX_AGE,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


# === FN-AUTH-SIGNUP ===
@router.post("/register", operation_id="API-AUTH-REGISTER", status_code=201)
async def register(
    request: Request,
    data: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    FN-AUTH-SIGNUP: Зарегистрировать пользователя
    """
    try:
        user, profile = await auth_service.register(
            display_name=data.display_name,
            email=data.email,
            password=data.password,
            consent=data.consent.model_dump(),
        )
        
        return success_response(
            data={
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "authStatus": user.auth_status.value,
                },
                "verification": {
                    "required": True,
                    "resendAfterSec": 60,
                }
            },
            request_id=request.state.request_id
        )
    except AppError as e:
        raise handle_app_error(e, request)


# === FN-AUTH-LOGIN ===
@router.post("/login", operation_id="API-AUTH-LOGIN")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    FN-AUTH-LOGIN: Войти в систему
    """
    try:
        user, profile, session_token, csrf_token = await auth_service.login(
            email=data.email,
            password=data.password,
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.client.host if request.client else None,
        )
        
        # Устанавливаем session cookie
        set_session_cookie(response, session_token)
        
        # CSRF токен возвращаем в ответе (frontend должен хранить в памяти)
        return success_response(
            data={
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "authStatus": user.auth_status.value,
                },
                "profile": {
                    "displayName": profile.display_name,
                    "timezone": profile.timezone,
                    "language": profile.language,
                },
                "csrfToken": csrf_token,
            },
            request_id=request.state.request_id
        )
    except AppError as e:
        raise handle_app_error(e, request)


# === FN-AUTH-RESTORE ===
@router.post("/password/restore-requests", operation_id="API-AUTH-RESTORE", status_code=202)
async def restore_password(
    request: Request,
    data: RestoreRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    FN-AUTH-RESTORE: Запросить восстановление пароля
    Всегда возвращает одинаковый ответ, чтобы не раскрывать наличие аккаунта
    """
    try:
        await auth_service.request_password_restore(data.email)
        
        return success_response(
            data={
                "accepted": True,
                "resendAfterSec": 60,
            },
            request_id=request.state.request_id
        )
    except AppError as e:
        raise handle_app_error(e, request)


# === FN-AUTH-RESET ===
@router.post("/password/resets", operation_id="API-AUTH-RESET")
    request: Request,
    data: ResetPasswordRequest,
    FN-AUTH-RESET: Установить новый пароль по одноразовой ссылке
        
        return success_response(
            data={
                "passwordChanged": True,
                "loginRequired": True,
            },
            request_id=request.state.request_id
        )
    except AppError as e:
        raise handle_app_error(e, request)


# === FN-AUTH-VERIFY ===
@router.post("/email/verifications", operation_id="API-AUTH-VERIFY")
async def verify_email(
    request: Request,
    response: Response,
    data: VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    FN-AUTH-VERIFY: Подтвердить email
    """
    try:
        user, profile = await auth_service.verify_email(data.token)
        
        # Создаем сессию после подтверждения (автологин)
        session_token = None
        try:
            _, _, session_token, csrf_token = await auth_service.login(
                email=user.email,
                password="",  # уже верифицирован
            )
        except AppError:
            # Если логин не удался, не страшно — пользователь может войти вручную
            pass
        
        if session_token:
            set_session_cookie(response, session_token)
        
        return success_response(
            data={
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "authStatus": user.auth_status.value,
                },
                "profile": {
                    "displayName": profile.display_name,
                    "timezone": profile.timezone,
                    "language": profile.language,
                } if profile else None,
            },
            request_id=request.state.request_id
        )
    except AppError as e:
        raise handle_app_error(e, request)


# === FN-AUTH-LOGOUT ===
@router.post("/logout", operation_id="API-AUTH-LOGOUT", status_code=204)
async def logout(
    request: Request,
    response: Response,
    data: LogoutRequest,
            token=data.token,
            new_password=data.new_password,
        )
    current_user: User = Depends(get_current_user),
    """
    try:
        await auth_service.reset_password(
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    FN-AUTH-LOGOUT: Выйти из системы
    """

    session_cookie = request.cookies.get("session_id", "")

    
    await auth_service.logout(

        session_token=session_cookie,
        user_id=current_user.id,

        all_sessions=data.all_sessions,
    )
    

    # Очищаем cookie
    response.delete_cookie("session_id", path="/")
    
    return None
