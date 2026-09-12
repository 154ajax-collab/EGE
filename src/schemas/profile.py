from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


VALID_FORMATS = {"video", "audio", "article", "official_document", "interactive"}


class ProfileResponse(BaseModel):
    display_name: str = Field(..., alias="displayName")
    certificate_name: Optional[str] = Field(None, alias="certificateName")
    timezone: str
    language: str
    preferred_formats: List[str] = Field(..., alias="preferredFormats")
    weekly_reminder_enabled: bool = Field(..., alias="weeklyReminderEnabled")
    version: int
    
    class Config:
        populate_by_name = True


class ProfilePatchRequest(BaseModel):
    display_name: Optional[str] = Field(None, alias="displayName", min_length=1, max_length=100)
    certificate_name: Optional[str] = Field(None, alias="certificateName", max_length=100)
    timezone: Optional[str] = None
    preferred_formats: Optional[List[str]] = Field(None, alias="preferredFormats")
    weekly_reminder_enabled: Optional[bool] = Field(None, alias="weeklyReminderEnabled")
    
    class Config:
        populate_by_name = True
    
    @field_validator("preferred_formats")
    @classmethod
    def validate_formats(cls, v):
        if v is not None:
            invalid = set(v) - VALID_FORMATS
            if invalid:
                raise ValueError(f"Недопустимые форматы: {invalid}")
        return v


class TrackCard(BaseModel):
    id: str
    title: str
    status: str
    progress_percent: float = Field(..., alias="progressPercent")
    current_topic: Optional[dict] = Field(None, alias="currentTopic")
    next_action: Optional[str] = Field(None, alias="nextAction")
    next_deadline: Optional[datetime] = Field(None, alias="nextDeadline")
    risk_status: Optional[str] = Field(None, alias="riskStatus")
    version: int
    
    class Config:
        populate_by_name = True


class DashboardSummary(BaseModel):
    active_track_count: int = Field(..., alias="activeTrackCount")
    attention_count: int = Field(..., alias="attentionCount")
    next_deadline: Optional[datetime] = Field(None, alias="nextDeadline")
    
    class Config:
        populate_by_name = True


class DeletionRequestBody(BaseModel):
    confirmation: str
    reason: Optional[str] = None
    
    @field_validator("confirmation")
    @classmethod
    def validate_confirmation(cls, v):
        if v != "DELETE":
            raise ValueError("confirmation must be 'DELETE'")
        return v


class DeletionCancelBody(BaseModel):
    password: str
