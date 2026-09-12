from fastapi import APIRouter, Request, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.core.database import get_db
from src.core.response import success_response, error_response
from src.core.exceptions import AppError, ErrorCode
from src.api.dependencies import get_current_user
from src.models.user import User
from src.services.profile_service import ProfileService
from src.schemas.profile import ProfilePatchRequest
from src.api.v1.auth import handle_app_error

router = APIRouter()


def serialize_profile(profile) -> dict:
    return {
        "displayName": profile.display_name,
        "certificateName": profile.certificate_name,
        "timezone": profile.timezone,
        "language": profile.language,
        "preferredFormats": profile.preferred_formats or [],
        "weeklyReminderEnabled": profile.weekly_reminder_enabled,
        "version": profile.version,
    }


@router.get("/me/profile", operation_id="API-PROFILE-GET")
async def get_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProfileService(db)
    profile = await service.get_profile(current_user.id)
    return success_response(
        data=serialize_profile(profile),
        request_id=request.state.request_id,
    )


@router.patch("/me/profile", operation_id="API-PROFILE")
async def update_profile(
    request: Request,
    data: ProfilePatchRequest,
    if_match: Optional[str] = Header(None, alias="If-Match"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-PROFILE-SAVE"""
    if not if_match:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message="Заголовок If-Match обязателен",
                request_id=request.state.request_id,
            )
        )
    
    try:
        expected_version = int(if_match.strip('"'))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message="If-Match должен содержать версию",
                request_id=request.state.request_id,
            )
        )
    
    service = ProfileService(db)
    try:
        # exclude_unset — обновляем только переданные поля
        profile = await service.update_profile(
            current_user.id,
            expected_version,
            data.model_dump(exclude_unset=True, by_alias=False),
        )
        return success_response(
            data=serialize_profile(profile),
            request_id=request.state.request_id,
        )
    except AppError as e:
        raise handle_app_error(e, request)