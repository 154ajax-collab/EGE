from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.response import success_response
from src.core.exceptions import AppError
from src.api.dependencies import get_current_user
from src.models.user import User
from src.services.deletion_service import DeletionService
from src.schemas.profile import DeletionRequestBody, DeletionCancelBody
from src.api.v1.auth import handle_app_error

router = APIRouter()


@router.post("/me/deletion-requests", operation_id="API-ACCOUNT-DELETE", status_code=202)
async def request_deletion(
    request: Request,
    data: DeletionRequestBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-ACCOUNT-DELETE-REQUEST"""
    service = DeletionService(db)
    try:
        req = await service.request_deletion(current_user.id, data.reason)
        return success_response(
            data={
                "requestId": str(req.id),
                "status": req.status.value,
                "requestedAt": req.requested_at.isoformat(),
                "scheduledDeletionAt": req.scheduled_deletion_at.isoformat(),
                "canRestoreUntil": req.can_restore_until.isoformat(),
            },
            request_id=request.state.request_id,
        )
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/me/deletion-requests/{request_id}/cancel", operation_id="API-ACCOUNT-DELETE-CANCEL")
async def cancel_deletion(
    request: Request,
    request_id: str,
    data: DeletionCancelBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DeletionService(db)
    try:
        import uuid as _uuid
        req = await service.cancel_deletion(
            current_user.id, _uuid.UUID(request_id), data.password
        )
        return success_response(
            data={
                "requestId": str(req.id),
                "status": req.status.value,
            },
            request_id=request.state.request_id,
        )
    except AppError as e:
        raise handle_app_error(e, request)