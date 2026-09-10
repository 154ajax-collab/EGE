from sqlalchemy import (
    String, DateTime, Enum as SQLEnum, JSON, ForeignKey, Integer, Float, Boolean,
    Text, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from typing import Optional, List
import uuid
import enum

from src.core.database import BaseModel


class PlanStatus(str, enum.Enum):
    """Статус плана (раздел 4 ТЗ)"""
    COLLECTING = "collecting"
    READY = "ready"
    GENERATING = "generating"
    DRAFT = "draft"
    APPROVED = "approved"
    FAILED = "failed"


class TrackStatus(str, enum.Enum):
    """Статус трека (раздел 4 ТЗ)"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TopicStatus(str, enum.Enum):
    """Статус темы (раздел 4 ТЗ)"""
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    READY_FOR_EXAM = "ready_for_exam"
    PASSED = "passed"


class MaterialVerificationStatus(str, enum.Enum):
    """Статус верификации материала (раздел 4 ТЗ)"""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BROKEN = "broken"


class GapSeverity(str, enum.Enum):
    """Серьезность пробела (раздел 4 ТЗ)"""
    INFO = "info"
    WARNING = "warning"


class DeadlineRisk(str, enum.Enum):
    """Риск дедлайна (раздел 4 ТЗ)"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNAVAILABLE = "unavailable"


class LearningGoal(BaseModel):
    """Цель обучения (раздел 4 ТЗ)"""
    __tablename__ = "learning_goals"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    skill: Mapped[str] = mapped_column(String(160))
    target_outcome: Mapped[str] = mapped_column(String(1000))
    current_level: Mapped[CurrentLevel] = mapped_column(SQLEnum(CurrentLevel))
    target_date: Mapped[date] = mapped_column()
    hours_per_week: Mapped[float] = mapped_column(Float)
    preferred_formats: Mapped[List[str]] = mapped_column(JSON, default=list)
    constraints: Mapped[List[str]] = mapped_column(JSON, default=list)
    deadline_risk: Mapped[Optional[DeadlineRisk]] = mapped_column(
        SQLEnum(DeadlineRisk),
        nullable=True
    )
    accepted_risk: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связи
    user: Mapped["User"] = relationship("User")
    plans: Mapped[List["PlanDraft"]] = relationship("PlanDraft", back_populates="goal")


class PlanDraft(BaseModel):
    """Черновик программы (раздел 4 ТЗ)"""
    __tablename__ = "plan_drafts"

    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_goals.id"))
    status: Mapped[PlanStatus] = mapped_column(
        SQLEnum(PlanStatus),
        default=PlanStatus.COLLECTING
    )
    assumptions: Mapped[List[str]] = mapped_column(JSON, default=list)
    gaps: Mapped[List[dict]] = mapped_column(JSON, default=list)  # Gap[] из ТЗ
    topics_data: Mapped[List[dict]] = mapped_column(JSON, default=list)  # TopicDraft[]

    # Связи
    goal: Mapped["LearningGoal"] = relationship("LearningGoal", back_populates="plans")
    track: Mapped[Optional["LearningTrack"]] = relationship(
        "LearningTrack",
        back_populates="plan",
        uselist=False
    )


class LearningTrack(BaseModel):
    """Учебный трек (раздел 4 ТЗ)"""
    __tablename__ = "learning_tracks"

    title: Mapped[str] = mapped_column(String(255))
    goal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_goals.id"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_drafts.id"))
    plan_version: Mapped[int] = mapped_column()
    status: Mapped[TrackStatus] = mapped_column(
        SQLEnum(TrackStatus),
        default=TrackStatus.ACTIVE
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    current_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("topics.id"),
        nullable=True
    )
    next_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Связи
    goal: Mapped["LearningGoal"] = relationship("LearningGoal")
    plan: Mapped["PlanDraft"] = relationship("PlanDraft", back_populates="track")
    topics: Mapped[List["Topic"]] = relationship("Topic", back_populates="track")
    current_topic: Mapped[Optional["Topic"]] = relationship(
        "Topic",
        foreign_keys=[current_topic_id]
    )


class Topic(BaseModel):
    """Тема обучения (раздел 4 ТЗ)"""
    __tablename__ = "topics"

    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_tracks.id"))
    title: Mapped[str] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer)
    prerequisite_topic_ids: Mapped[List[uuid.UUID]] = mapped_column(JSON, default=list)
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    status: Mapped[TopicStatus] = mapped_column(
        SQLEnum(TopicStatus),
        default=TopicStatus.LOCKED
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    exam_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("exams.id"),
        nullable=True
    )

    # Связи
    track: Mapped["LearningTrack"] = relationship("LearningTrack", back_populates="topics")
    materials: Mapped[List["LearningMaterial"]] = relationship(
        "LearningMaterial",
        back_populates="topic"
    )
    exam: Mapped[Optional["Exam"]] = relationship("Exam", foreign_keys=[exam_id])


class LearningMaterial(BaseModel):
    """Учебный материал (раздел 4 ТЗ)"""
    __tablename__ = "learning_materials"

    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String(1000))
    domain: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), default="ru")
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_status: Mapped[MaterialVerificationStatus] = mapped_column(
        SQLEnum(MaterialVerificationStatus),
        default=MaterialVerificationStatus.UNVERIFIED
    )
    checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Связи
    topic: Mapped["Topic"] = relationship("Topic", back_populates="materials")