import uuid
from fastapi import APIRouter, Request, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.response import success_response
from src.core.exceptions import AppError, ErrorCode
from src.api.dependencies import get_current_user
from src.api.v1.auth import handle_app_error
from src.models.user import User
from src.services.plan_service import PlanService
from src.adapters.ai_adapter import get_ai_adapter
from src.schemas.plan import (
    PlanInterviewCreate, BriefFieldPatch, DeadlineEvaluateRequest,
    PlanGenerateBody, PlanApproveBody,
)

router = APIRouter()


def serialize_plan(plan, goal) -> dict:
    required = ["skill", "targetOutcome", "hoursPerWeek"]
    missing = []
    if not goal.skill or len(goal.skill) < 2:
        missing.append("skill")
    if not goal.target_outcome or len(goal.target_outcome) < 5:
        missing.append("targetOutcome")
    if goal.hours_per_week <= 0:
        missing.append("hoursPerWeek")
    
    return {
        "id": str(plan.id),
        "status": plan.status.value,
        "currentStep": "brief" if missing else "review",
        "brief": {
            "skill": goal.skill,
            "targetOutcome": goal.target_outcome,
            "currentLevel": goal.current_level.value if goal.current_level else None,
            "targetDate": goal.target_date.isoformat() if goal.target_date else None,
            "hoursPerWeek": goal.hours_per_week,
            "preferredFormats": goal.preferred_formats or [],
            "constraints": goal.constraints or [],
            "acceptedRisk": goal.accepted_risk,
            "deadlineRisk": goal.deadline_risk.value if goal.deadline_risk else None,
        },
        "completion": {
            "requiredFields": required,
            "missingFields": missing,
        },
        "assumptions": plan.assumptions or [],
        "gaps": plan.gaps or [],
        "topics": plan.topics_data or [],
        "version": plan.version,
    }


@router.post("/plan-interviews", operation_id="API-PLAN-INTERVIEW-CREATE", status_code=201)
async def create_interview(
    request: Request,
    data: PlanInterviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-PLAN-RESUME — создать интервью"""
    service = PlanService(db, get_ai_adapter())
    plan = await service.create_or_get_interview(current_user.id)
    goal = await service._get_goal(plan.goal_id)
    return success_response(serialize_plan(plan, goal), request.state.request_id)


@router.get("/plan-interviews/{interview_id}", operation_id="API-PLAN-INTERVIEW-GET")
async def get_interview(
    request: Request,
    interview_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-PLAN-RESUME — продолжить интервью"""
    service = PlanService(db, get_ai_adapter())
    try:
        plan = await service._get_owned_plan(uuid.UUID(interview_id), current_user.id)
        goal = await service._get_goal(plan.goal_id)
        return success_response(serialize_plan(plan, goal), request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.patch("/plan-interviews/{interview_id}/brief", operation_id="API-PLAN-BRIEF")
async def save_brief(
    request: Request,
    interview_id: str,
    data: BriefFieldPatch,
    if_match: str = Header(..., alias="If-Match"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-PLAN-BRIEF-SAVE"""
    try:
        expected_version = int(if_match.strip('"'))
    except ValueError:
        raise HTTPException(400, "Invalid If-Match")
    
    service = PlanService(db, get_ai_adapter())
    try:
        plan, goal = await service.save_brief_field(
            uuid.UUID(interview_id), current_user.id,
            data.field, data.value, expected_version,
        )
        return success_response(serialize_plan(plan, goal), request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/deadline-evaluations", operation_id="API-DEADLINE-EVALUATE")
async def evaluate_deadline(
    request: Request,
    data: DeadlineEvaluateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-DEADLINE-EVALUATE"""
    service = PlanService(db, get_ai_adapter())
    result = await service.evaluate_deadline({
        "skill": data.skill,
        "targetOutcome": data.target_outcome,
        "currentLevel": data.current_level,
        "targetDate": data.target_date.isoformat(),
        "hoursPerWeek": data.hours_per_week,
    })
    return success_response(result, request.state.request_id)


@router.post("/plan-interviews/{interview_id}/generation-jobs",
             operation_id="API-PLAN-GENERATE", status_code=202)
async def generate_plan(
    request: Request,
    interview_id: str,
    data: PlanGenerateBody,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-PLAN-GENERATE (синхронно для MVP)"""
    service = PlanService(db, get_ai_adapter())
    try:
        plan = await service.generate_plan(
            uuid.UUID(interview_id), current_user.id,
            data.brief_version, data.accepted_assumption_ids,
        )
        return success_response({
            "id": f"job-{plan.id}",
            "type": "plan_generation",
            "status": "succeeded",
            "stage": "completed",
            "progressPercent": 100,
            "resourceType": "plan",
            "resourceId": str(plan.id),
            "error": None,
        }, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/plans/{plan_id}/approve", operation_id="API-PLAN-APPROVE", status_code=201)
async def approve_plan(
    request: Request,
    plan_id: str,
    data: PlanApproveBody,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-PLAN-APPROVE"""
    service = PlanService(db, get_ai_adapter())
    try:
        track = await service.approve_plan(
            uuid.UUID(plan_id), current_user.id,
            data.expected_plan_version, data.acknowledgements,
        )
        return success_response({
            "id": str(track.id),
            "title": track.title,
            "status": track.status.value,
            "progressPercent": track.progress_percent,
            "currentAction": "start_first_topic",
            "version": track.version,
        }, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)