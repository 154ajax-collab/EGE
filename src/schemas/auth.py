from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List


class ConsentSchema(BaseModel):
    terms_version: str = Field(..., alias="termsVersion")
    privacy_version: str = Field(..., alias="privacyVersion")
    accepted_at: datetime = Field(..., alias="acceptedAt")

    class Config:
        populate_by_name = True


class RegisterRequest(BaseModel):
    display_name: str = Field(..., alias="displayName", min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    consent: ConsentSchema

    class Config:
        populate_by_name = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
        if not any(c.isdigit() for c in v):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        return v


class UserShortResponse(BaseModel):
    id: str
    email: str
    auth_status: str = Field(..., alias="authStatus")

    class Config:
        populate_by_name = True


class VerificationInfo(BaseModel):
    required: bool = True
    resend_after_sec: int = Field(60, alias="resendAfterSec")

    class Config:
        populate_by_name = True


class RegisterResponse(BaseModel):
    user: UserShortResponse
    verification: VerificationInfo


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    return_path: Optional[str] = Field(None, alias="returnPath")

    class Config:
        populate_by_name = True


class ProfileShortResponse(BaseModel):
    display_name: str = Field(..., alias="displayName")
    timezone: str
    language: str

    class Config:
        populate_by_name = True


class LoginResponse(BaseModel):
    user: UserShortResponse
    profile: ProfileShortResponse


class RestoreRequest(BaseModel):
    email: EmailStr


class RestoreResponse(BaseModel):
    accepted: bool = True
    resend_after_sec: int = Field(60, alias="resendAfterSec")

    class Config:
        populate_by_name = True


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., alias="newPassword", min_length=8, max_length=128)

    class Config:
        populate_by_name = True


class ResetPasswordResponse(BaseModel):
    password_changed: bool = Field(True, alias="passwordChanged")
    login_required: bool = Field(True, alias="loginRequired")

    class Config:
        populate_by_name = True


class VerifyEmailRequest(BaseModel):
    token: str


class LogoutRequest(BaseModel):
    all_sessions: bool = Field(False, alias="allSessions")

    class Config:
        populate_by_name = True