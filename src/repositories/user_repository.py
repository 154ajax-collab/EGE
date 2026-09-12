from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from src.models.user import User, Profile, AuthStatus


class UserRepository:
    """Репозиторий для работы с пользователями"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()
    
    async def create(self, email: str, password_hash: str) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            auth_status=AuthStatus.PENDING,
        )
        self.db.add(user)
        await self.db.flush()
        return user
    
    async def create_profile(self, user_id: uuid.UUID, display_name: str) -> Profile:
        profile = Profile(
            user_id=user_id,
            display_name=display_name,
            timezone="Europe/Moscow",
            language="ru",
            preferred_formats=[],
            weekly_reminder_enabled=True,
        )
        self.db.add(profile)
        await self.db.flush()
        return profile
    
    async def get_profile(self, user_id: uuid.UUID) -> Optional[Profile]:
        result = await self.db.execute(
            select(Profile).where(Profile.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_last_login(self, user_id: uuid.UUID) -> None:
        from datetime import datetime, timezone
        user = await self.get_by_id(user_id)
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()
