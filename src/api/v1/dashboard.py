from fastapi import APIRouter, Request, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.response import success_response, PaginationMeta
from src.api.dependencies import get_current_user
from src.models.user import User
from src.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/dashboard", operation_id="API-DASHBOARD")
async def load_dashboard(
    request: Request,
    filter: str = Query("active", regex="^(active|attention|completed)$"),
    cursor: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FN-DASHBOARD-LOAD"""
    service = DashboardService(db)
    data = await service.load_dashboard(current_user.id, filter)
    
    return success_response(
        data=data,
        request_id=request.state.request_id,
        pagination=PaginationMeta(next_cursor=None, has_more=False),
    )