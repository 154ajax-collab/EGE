from sqlalchemy import (
    String, DateTime, Enum as SQLEnum, JSON, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
import uuid
import enum

from src.core.database import BaseModel


class ChatPurpose(str, enum.Enum):
    """Назначение чата (раздел 4 ТЗ)"""
    INTERVIEW = "interview"
    PLAN_REVIEW = "plan_review"
    TUTOR = "tutor"
    PRACTICE = "practice"


class MessageRole(str, enum.Enum):
    """Роль в сообщении (раздел 4 ТЗ)"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatThread(BaseModel):
    """Поток чата (раздел 4 ТЗ)"""
    __tablename__ = "chat_threads"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    track_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("learning_tracks.id"),
        nullable=True
    )
    plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("plan_drafts.id"),
        nullable=True
    )
    purpose: Mapped[ChatPurpose] = mapped_column(
        SQLEnum(ChatPurpose),
        default=ChatPurpose.TUTOR
    )
    context_version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(50), default="active")

    # Связи
    user: Mapped["User"] = relationship("User")
    track: Mapped[Optional["LearningTrack"]] = relationship("LearningTrack")
    plan: Mapped[Optional["PlanDraft"]] = relationship("PlanDraft")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="thread"
    )


class ChatMessage(BaseModel):
    """Сообщение чата (раздел 4 ТЗ)"""
    __tablename__ = "chat_messages"

    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_threads.id"))
    role: Mapped[MessageRole] = mapped_column(SQLEnum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    references: Mapped[List[dict]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="sent")

    # Связи
    thread: Mapped["ChatThread"] = relationship("ChatThread", back_populates="messages")