from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AppError, ErrorCode
from src.core.security import verify_password
from src.models.user import User, AuthStatus
from src.models.deletion import DeletionRequest, DeletionStatus
from src.models.auth import Session


class DeletionService:
    """FN-ACCOUNT-DELETE-REQUEST (раздел 6.2 ТЗ)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def request_deletion(
        self,
        user_id: uuid.UUID,
        reason: str = None,
    ) -> DeletionRequest:
        # Проверяем, нет ли уже активного запроса
        result = await self.db.execute(
            select(DeletionRequest).where(
                DeletionRequest.user_id == user_id,
                DeletionRequest.status.in_([DeletionStatus.REQUESTED, DeletionStatus.SCHEDULED]),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        
        now = datetime.now(timezone.utc)
        scheduled = now + timedelta(days=settings.DELETION_GRACE_PERIOD_DAYS)
        
        # Создаем запрос
        request = DeletionRequest(
            user_id=user_id,
            status=DeletionStatus.REQUESTED,
            reason=reason,
            requested_at=now,
            scheduled_deletion_at=scheduled,
            can_restore_until=scheduled,
        )
        self.db.add(request)
        
        # Обновляем пользователя
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one()
        user.auth_status = AuthStatus.DELETION_PENDING
        user.deleted_at = now
        user.restore_deadline = scheduled
        
        # Отзываем все сессии
        sessions_result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
            )
        )
        for session in sessions_result.scalars().all():
            session.revoked_at = now
        
        await self.db.commit()
        return request
    
    async def cancel_deletion(
        self,
        user_id: uuid.UUID,
        request_id: uuid.UUID,
        password: str,
    ) -> DeletionRequest:
        # Получаем запрос
        result = await self.db.execute(
            select(DeletionRequest).where(
                DeletionRequest.id == request_id,
                DeletionRequest.user_id == user_id,
            )
        )
        request = result.scalar_one_or_none()
        if not request:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Запрос на удаление не найден",
                status_code=404,
            )
        
        if request.status not in [DeletionStatus.REQUESTED, DeletionStatus.SCHEDULED]:
            raise AppError(
                code=ErrorCode.STATE_CONFLICT,
                message="Запрос уже завершён",
                status_code=409,
            )
        
        # Проверяем пароль
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one()
        if not verify_password(password, user.password_hash):
            raise AppError(
                code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Неверный пароль",
                status_code=401,
            )
        
        # Отменяем
        request.status = DeletionStatus.CANCELLED
        request.cancelled_at = datetime.now(timezone.utc)
        
        user.auth_status = AuthStatus.ACTIVE
        user.deleted_at = None
        user.restore_deadline = None
        
        await self.db.commit()
        return request