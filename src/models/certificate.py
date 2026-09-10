from sqlalchemy import (
    String, DateTime, Enum as SQLEnum, JSON, ForeignKey, Integer, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
import uuid
import enum

from src.core.database import BaseModel


class CertificateStatus(str, enum.Enum):
    """Статус сертификата (раздел 4 ТЗ)"""
    QUEUED = "queued"
    GENERATING = "generating"
    ISSUED = "issued"
    FAILED = "failed"


class Certificate(BaseModel):
    """Сертификат (раздел 4 ТЗ)"""
    __tablename__ = "certificates"

    track_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_tracks.id"))
    certificate_name: Mapped[str] = mapped_column(String(100))
    skill_name: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    document_no: Mapped[str] = mapped_column(String(50), unique=True)
    template_version: Mapped[str] = mapped_column(String(20))
    legal_text_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[CertificateStatus] = mapped_column(
        SQLEnum(CertificateStatus),
        default=CertificateStatus.QUEUED
    )
    preview_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Связи
    track: Mapped["LearningTrack"] = relationship("LearningTrack")