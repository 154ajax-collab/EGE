from sqlalchemy import (
    String, DateTime, Enum as SQLEnum, JSON, ForeignKey, Integer, Float,
    Boolean, Text, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
import uuid
import enum

from src.core.database import BaseModel


class AttemptStatus(str, enum.Enum):
    """Статус попытки экзамена (раздел 4 ТЗ)"""
    ACTIVE = "active"
    SUBMITTED = "submitted"
    EVALUATING = "evaluating"
    PASSED = "passed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class QuestionType(str, enum.Enum):
    """Тип вопроса (раздел 4 ТЗ)"""
    SINGLE = "single"
    MULTIPLE = "multiple"
    TEXT = "text"


class Exam(BaseModel):
    """Экзамен (раздел 4 ТЗ)"""
    __tablename__ = "exams"

    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_tracks.id"))
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String(255))
    criteria: Mapped[dict] = mapped_column(JSON)  # Критерии оценки
    passing_percent: Mapped[int] = mapped_column(Integer, default=80)
    max_attempts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cooldown_sec: Mapped[int] = mapped_column(Integer, default=0)
    time_limit_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    question_count: Mapped[int] = mapped_column(Integer)
    final: Mapped[bool] = mapped_column(Boolean, default=False)
    questions_snapshot: Mapped[List[dict]] = mapped_column(JSON, default=list)  # Замороженные вопросы

    # Связи
    track: Mapped["LearningTrack"] = relationship("LearningTrack")
    topic: Mapped["Topic"] = relationship("Topic")
    attempts: Mapped[List["ExamAttempt"]] = relationship(
        "ExamAttempt",
        back_populates="exam"
    )


class ExamAttempt(BaseModel):
    """Попытка экзамена (раздел 4 ТЗ)"""
    __tablename__ = "exam_attempts"

    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id"))
    status: Mapped[AttemptStatus] = mapped_column(
        SQLEnum(AttemptStatus),
        default=AttemptStatus.ACTIVE
    )
    rubric_version: Mapped[int] = mapped_column(default=1)
    answers: Mapped[List[dict]] = mapped_column(JSON, default=list)  # ExamAnswer[]
    score_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Обратная связь
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Связи
    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")