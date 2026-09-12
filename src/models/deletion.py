from sqlalchemy import String, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
import uuid
import enum

from src.core.database import BaseModel


class DeletionStatus(str, enum.Enum):
    REQUESTED = "requested"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"


class DeletionRequest(BaseModel):
    """Запрос на удаление аккаунта (раздел 6.2 ТЗ)"""
    __tablename__ = "deletion_requests"
    
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[DeletionStatus] = mapped_column(
        SQLEnum(DeletionStatus),
        default=DeletionStatus.REQUESTED
    )
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_deletion_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    can_restore_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
