import uuid
from fastapi import APIRouter, Request, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.response import success_response
from src.core.exceptions import AppError
from src.api.dependencies import get_current_user
from src.api.v1.auth import handle_app_error
from src.models.user import User
from src.services.exam_service import ExamService
from src.adapters.ai_adapter import get_ai_adapter

router = APIRouter()


def svc(db):
    return ExamService(db, get_ai_adapter())


@router.get("/exams/{exam_id}", operation_id="API-EXAM-INTRO")
async def get_exam(
    request: Request,
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await svc(db).get_exam_intro(uuid.UUID(exam_id), current_user.id)
        return success_response(data, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/exams/{exam_id}/attempts", operation_id="API-EXAM-START")
async def start_attempt(
    request: Request,
    exam_id: str,
    data: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).start_attempt(
            uuid.UUID(exam_id), current_user.id,
            data.get("resumeIfActive", True),
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.put("/exam-attempts/{attempt_id}/answers/{question_id}",
            operation_id="API-EXAM-ANSWER")
async def save_answer(
    request: Request,
    attempt_id: str,
    question_id: str,
    data: dict,
    if_match: str = Header(..., alias="If-Match"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        version = int(if_match.strip('"'))
        result = await svc(db).save_answer(
            uuid.UUID(attempt_id), question_id, current_user.id, data, version,
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/exam-attempts/{attempt_id}/submit",
             operation_id="API-EXAM-SUBMIT", status_code=202)
async def submit(
    request: Request,
    attempt_id: str,
    data: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).submit(
            uuid.UUID(attempt_id), current_user.id,
            data.get("expectedVersion", 1),
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.get("/exam-attempts/{attempt_id}", operation_id="API-EXAM-RESULT")
async def get_result(
    request: Request,
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).get_result(uuid.UUID(attempt_id), current_user.id)
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)