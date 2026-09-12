from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid
from datetime import datetime, timezone

from src.core.config import settings
from src.core.exceptions import AppError
from src.core.response import error_response
from src.api.v1 import auth
from src.models.deletion import DeletionRequest, DeletionStatus
from src.api.v1 import (
    auth, dashboard, profile, account, plans, learning, exams, tutor, certificates
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["auth"])
app.include_router(dashboard.router, prefix=settings.API_PREFIX, tags=["dashboard"])
app.include_router(profile.router, prefix=settings.API_PREFIX, tags=["profile"])
app.include_router(account.router, prefix=settings.API_PREFIX, tags=["account"])
app.include_router(plans.router, prefix=settings.API_PREFIX, tags=["plans"])
app.include_router(learning.router, prefix=settings.API_PREFIX, tags=["learning"])
app.include_router(exams.router, prefix=settings.API_PREFIX, tags=["exams"])
app.include_router(tutor.router, prefix=settings.API_PREFIX, tags=["tutor"])
app.include_router(certificates.router, prefix=settings.API_PREFIX, tags=["certificates"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# Обработчик кастомных ошибок
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            code=exc.code,
            message=exc.message,
            request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
            field_errors=exc.field_errors,
            details=exc.details,
            retryable=exc.retryable,
        )
    )


# Обработчик ошибок валидации Pydantic
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    field_errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"][1:])  # убираем "body"
        field_errors.append({
            "field": field_path or "body",
            "code": error["type"].upper(),
            "message": error["msg"],
        })
    
    return JSONResponse(
        status_code=400,
        content=error_response(
            code="VALIDATION_ERROR",
            message="Проверьте заполненные поля",
            request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
            field_errors=field_errors,
        )
    )


app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["auth"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs"
    }
