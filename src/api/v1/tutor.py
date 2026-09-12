import uuid
from fastapi import APIRouter, Request, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.core.database import get_db
from src.core.response import success_response
from src.core.exceptions import AppError
from src.api.dependencies import get_current_user
from src.api.v1.auth import handle_app_error
from src.models.user import User
from src.services.tutor_service import TutorService
from src.adapters.ai_adapter import get_ai_adapter

router = APIRouter()


def svc(db):
    return TutorService(db, get_ai_adapter())


@router.post("/chat-threads", operation_id="API-CHAT-CREATE", status_code=201)
async def create_thread(
    request: Request,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thread = await svc(db).create_or_get_thread(current_user.id, data.get("purpose", "tutor"))
    return success_response({
        "id": str(thread.id),
        "purpose": thread.purpose.value,
        "contextVersion": thread.context_version,
    }, request.state.request_id)


@router.patch("/chat-threads/{thread_id}/context", operation_id="API-CHAT-CONTEXT")
async def set_context(
    request: Request,
    thread_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        thread = await svc(db).set_context(
            uuid.UUID(thread_id), current_user.id,
            data.get("topicId"), data.get("materialId"),
            data.get("expectedContextVersion", 1),
        )
        return success_response({
            "id": str(thread.id),
            "contextVersion": thread.context_version,
        }, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/chat-threads/{thread_id}/messages",
             operation_id="API-CHAT-SEND", status_code=202)
async def send_message(
    request: Request,
    thread_id: str,
    data: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).send_message(
            uuid.UUID(thread_id), current_user.id,
            data["text"], data.get("contextVersion", 1),
            data.get("clientMessageId", ""),
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.get("/chat-threads/{thread_id}/messages", operation_id="API-CHAT-HISTORY")
async def get_history(
    request: Request,
    thread_id: str,
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).get_history(uuid.UUID(thread_id), current_user.id, cursor)
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/chat-threads/{thread_id}/actions/summarize", operation_id="API-TUTOR-SUMMARIZE")
async def summarize(
    request: Request,
    thread_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).summarize(
            uuid.UUID(thread_id), current_user.id,
            data["materialId"], data.get("contextVersion", 1),
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/chat-threads/{thread_id}/actions/practice", operation_id="API-TUTOR-PRACTICE")
async def practice(
    request: Request,
    thread_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).practice(
            uuid.UUID(thread_id), current_user.id,
            data["topicId"], data.get("difficulty"),
            data.get("questionCount", 3), data.get("contextVersion", 1),
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/chat-messages/{message_id}/feedback", operation_id="API-TUTOR-FEEDBACK", status_code=204)
async def feedback(
    request: Request,
    message_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await svc(db).feedback(
            uuid.UUID(message_id), current_user.id,
            data["rating"], data.get("reasonCode"), data.get("comment"),
        )
        return None
    except AppError as e:
        raise handle_app_error(e, request)