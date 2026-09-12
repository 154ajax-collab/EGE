from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AppError, ErrorCode
from src.repositories.user_repository import UserRepository


class ProfileService:
    """FN-PROFILE-SAVE (раздел 6.2 ТЗ)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def get_profile(self, user_id: uuid.UUID):
        profile = await self.user_repo.get_profile(user_id)
        if not profile:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Профиль не найден",
                status_code=404,
            )
        return profile
    
    async def update_profile(
        self,
        user_id: uuid.UUID,
        expected_version: int,
        data: dict,
    ):
        profile = await self.user_repo.get_profile(user_id)
        if not profile:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Профиль не найден",
                status_code=404,
            )
        
        # Optimistic locking
        if profile.version != expected_version:
            raise AppError(
                code=ErrorCode.VERSION_CONFLICT,
                message="Профиль был изменён. Обновите страницу.",
                status_code=409,
                details={"currentVersion": profile.version},
            )
        
        # Обновляем только переданные поля
        for field in ["display_name", "certificate_name", "timezone",
                      "preferred_formats", "weekly_reminder_enabled"]:
            if field in data and data[field] is not None:
                setattr(profile, field, data[field])
        
        profile.version += 1
        await self.db.commit()
        return profile
