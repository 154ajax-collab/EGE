from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone
from typing import Optional

from src.core.response import success_response, error_response
from src.core.exceptions import AppError, ErrorCode

router = APIRouter()


# === Схемы ===

class ConsentSchema(BaseModel):
    terms_version: str = Field(..., alias="termsVersion")
    privacy_version: str = Field(..., alias="privacyVersion")
    accepted_at: datetime = Field(..., alias="acceptedAt")

    class Config:
        populate_by_name = True


class RegisterRequest(BaseModel):
    display_name: str = Field(..., alias="displayName", min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    consent: ConsentSchema

    class Config:
        populate_by_name = True


@router.post("/register", operation_id="API-AUTH-REGISTER", status_code=201)
async def register(request: Request, data: RegisterRequest):
    """
    FN-AUTH-SIGNUP: Зарегистрировать пользователя
    """
    try:
        # TODO: Реализовать регистрацию
        # 1. Нормализовать email
        # 2. Проверить уникальность
        # 3. Хешировать пароль
        # 4. Создать User и Profile
        # 5. Создать verification token
        # 6. Отправить email

        return success_response(
            data={
                "user": {
                    "id": "mock-user-id",
                    "email": data.email,
                    "authStatus": "pending_verification"
                },
                "verification": {
                    "required": True,
                    "resendAfterSec": 60
                }
            },
            request_id=request.state.request_id
        )
    except AppError as e:
        raise HTTPException(
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


@router.post("/login", operation_id="API-AUTH-LOGIN")
async def login(request: Request):
    """
    FN-AUTH-LOGIN: Войти в систему
    """
    # TODO: Реализовать логин
    return success_response(
        data={
            "user": {"id": "mock-id", "email": "user@example.com", "authStatus": "active"},
            "profile": {"displayName": "User", "timezone": "Europe/Moscow"}
        },
        request_id=request.state.request_id
    )


@router.post("/logout", operation_id="API-AUTH-LOGOUT", status_code=204)
async def logout():
    """
    FN-AUTH-LOGOUT: Выйти из системы
    """
    # TODO: Реализовать logout
    return None