from datetime import datetime, timezone
from typing import Optional, Any, List
from pydantic import BaseModel


class PaginationMeta(BaseModel):
    next_cursor: Optional[str] = None
    has_more: bool = False


class ResponseMeta(BaseModel):
    request_id: str
    timestamp: datetime = datetime.now(timezone.utc)
    page: Optional[PaginationMeta] = None


class ApiResponse(BaseModel):
    data: Any
    meta: ResponseMeta


class ErrorField(BaseModel):
    field: str
    code: str
    message: str


def success_response(data: Any, request_id: str, pagination: Optional[PaginationMeta] = None) -> dict:
    return {
        "data": data,
        "meta": {
            "requestId": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "page": pagination.model_dump() if pagination else None
        }
    }


def error_response(
    code: str,
    message: str,
    request_id: str,
    status_code: int = 400,
    field_errors: Optional[List[ErrorField]] = None,
    details: Optional[dict] = None,
    retryable: bool = False
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "fieldErrors": [fe.model_dump() for fe in field_errors] if field_errors else [],
            "details": details or {}
        },
        "meta": {
            "requestId": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }