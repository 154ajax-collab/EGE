import uuid
from fastapi import APIRouter, Request, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.response import success_response
from src.core.exceptions import AppError
from src.api.dependencies import get_current_user
from src.api.v1.auth import handle_app_error
from src.models.user import User
from src.services.learning_service import LearningService
from src.schemas.plan import MaterialIssueBody

router = APIRouter()


@router.get("/tracks/{track_id}", operation_id="API-TRACK")
async def open_track(
    request: Request,
    track_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-TRACK-OPEN"""
    service = LearningService(db)
    try:
        data = await service.get_track(uuid.UUID(track_id), current_user.id)
        return success_response(data, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.get("/tracks/{track_id}/topics/{topic_id}", operation_id="API-TOPIC")
async def open_topic(
    request: Request,
    track_id: str,
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-TOPIC-OPEN"""
    service = LearningService(db)
    try:
        data = await service.get_topic(
            uuid.UUID(track_id), uuid.UUID(topic_id), current_user.id
        )
        return success_response(data, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/materials/{material_id}/open-events", operation_id="API-MATERIAL-OPEN", status_code=204)
async def open_material(
    request: Request,
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-MATERIAL-OPEN"""
    service = LearningService(db)
    try:
        await service.register_material_open(uuid.UUID(material_id), current_user.id)
        return None
    except AppError as e:
        raise handle_app_error(e, request)


@router.put("/materials/{material_id}/completion", operation_id="API-PROGRESS")
async def complete_material(
    request: Request,
    material_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-MATERIAL-COMPLETE"""
    service = LearningService(db)
    try:
        result = await service.set_material_completion(
            uuid.UUID(material_id), current_user.id,
            data.get("completed", False), data.get("expectedVersion", 1),
        )
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.get("/tracks/{track_id}/stats", operation_id="API-STATS")
async def get_stats(
    request: Request,
    track_id: str,
    from_date: str = None,
    to_date: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-STATS-LOAD"""
    service = LearningService(db)
    try:
        data = await service.get_stats(uuid.UUID(track_id), current_user.id)
        return success_response(data, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)