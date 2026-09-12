from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from datetime import date, datetime


class PlanInterviewCreate(BaseModel):
    source: str = "dashboard"


class BriefFieldPatch(BaseModel):
    field: str
    value: Any
    
    @field_validator("field")
    @classmethod
    def validate_field(cls, v):
        allowed = {
            "skill", "targetOutcome", "currentLevel", "targetDate",
            "hoursPerWeek", "preferredFormats", "constraints", "acceptedRisk"
        }
        if v not in allowed:
            raise ValueError(f"Недопустимое поле: {v}")
        return v


class DeadlineEvaluateRequest(BaseModel):
    skill: str = Field(..., min_length=2, max_length=160)
    target_outcome: str = Field(..., alias="targetOutcome", min_length=5, max_length=1000)
    current_level: str = Field(..., alias="currentLevel")
    target_date: date = Field(..., alias="targetDate")
    hours_per_week: float = Field(..., alias="hoursPerWeek", gt=0)
    timezone: str
    
    class Config:
        populate_by_name = True


class PlanGenerateBody(BaseModel):
    brief_version: int = Field(..., alias="briefVersion")
    accepted_assumption_ids: List[str] = Field(default_factory=list, alias="acceptedAssumptionIds")
    
    class Config:
        populate_by_name = True


class PlanChangeRequestBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    base_plan_version: int = Field(..., alias="basePlanVersion")
    context_topic_ids: List[str] = Field(default_factory=list, alias="contextTopicIds")
    
    class Config:
        populate_by_name = True


class PlanApplyBody(BaseModel):
    expected_plan_version: int = Field(..., alias="expectedPlanVersion")
    
    class Config:
        populate_by_name = True


class PlanApproveBody(BaseModel):
    expected_plan_version: int = Field(..., alias="expectedPlanVersion")
    timezone: str
    acknowledgements: dict
    
    class Config:
        populate_by_name = True


class MaterialIssueBody(BaseModel):
    reason: str
    comment: Optional[str] = None
    
    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        allowed = {"broken_link", "wrong_language", "wrong_topic", "paid_or_closed", "other"}
        if v not in allowed:
            raise ValueError(f"Недопустимая причина: {v}")
        return v