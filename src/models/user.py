from sqlalchemy import String, DateTime, Enum as SQLEnum, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, List
import enum

from src.core.database import BaseModel


class AuthStatus(str, enum.Enum):
    """Статус авторизации пользователя (раздел 4 ТЗ)"""
    PENDING = "pending_verification"
    ACTIVE = "active"
    LOCKED = "locked"
    DELETION_PENDING = "deletion_pending"


class PreferredFormat(str, enum.Enum):
    """Предпочитаемые форматы материалов (раздел 4 ТЗ)"""
    VIDEO = "video"
    AUDIO = "audio"
    ARTICLE = "article"
    OFFICIAL_DOCUMENT = "official_document"
    INTERACTIVE = "interactive"


class CurrentLevel(str, enum.Enum):
    """Уровень подготовки (раздел 4 ТЗ)"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class User(BaseModel):
    """Модель пользователя (раздел 4 ТЗ)"""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    auth_status: Mapped[AuthStatus] = mapped_column(
        SQLEnum(AuthStatus),
        default=AuthStatus.PENDING
    )
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    restore_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Связи
    profile: Mapped["Profile"] = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )


class Profile(BaseModel):
    """Профиль пользователя (раздел 4 ТЗ)"""
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    certificate_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    language: Mapped[str] = mapped_column(String(2), default="ru")
    preferred_formats: Mapped[List[str]] = mapped_column(JSON, default=list)
    weekly_reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="profile")