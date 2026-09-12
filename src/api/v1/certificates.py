import uuid
from fastapi import APIRouter, Request, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.response import success_response
from src.core.exceptions import AppError
from src.api.dependencies import get_current_user
from src.api.v1.auth import handle_app_error
from src.models.user import User
from src.services.certificate_service import CertificateService
from src.adapters.renderer_adapter import get_renderer_adapter

router = APIRouter()


def svc(db):
    return CertificateService(db, get_renderer_adapter())


@router.post("/tracks/{track_id}/certificate-generation-jobs",
             operation_id="API-DIPLOMA-GENERATE", status_code=202)
async def generate_certificate(
    request: Request,
    track_id: str,
    data: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cert = await svc(db).generate_certificate(
            uuid.UUID(track_id), current_user.id,
            data["finalAttemptId"], data.get("profileVersion", 1),
            data.get("templateVersion", "1.0"),
            data.get("legalTextVersion", "1.0"),
        )
        return success_response({
            "id": f"job-{cert.id}",
            "type": "certificate_generation",
            "status": "succeeded" if cert.status.value == "issued" else "failed",
            "resourceType": "certificate",
            "resourceId": str(cert.id),
        }, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.get("/certificates/{cert_id}", operation_id="API-DIPLOMA-STATUS")
async def get_certificate(
    request: Request,
    cert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cert = await svc(db).get_certificate(uuid.UUID(cert_id), current_user.id)
        return success_response({
            "id": str(cert.id),
            "status": cert.status.value,
            "certificateName": cert.certificate_name,
            "skillName": cert.skill_name,
            "issueDate": cert.issue_date.isoformat() if cert.issue_date else None,
            "documentNo": cert.document_no,
            "previewUrl": cert.preview_url,
            "downloadAvailable": cert.status.value == "issued",
            "templateVersion": cert.template_version,
            "legalTextVersion": cert.legal_text_version,
            "version": cert.version,
        }, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.post("/certificates/{cert_id}/download-links",
             operation_id="API-DIPLOMA-DOWNLOAD")
async def get_download_link(
    request: Request,
    cert_id: str,
    data: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await svc(db).create_download_link(uuid.UUID(cert_id), current_user.id)
        return success_response(result, request.state.request_id)
    except AppError as e:
        raise handle_app_error(e, request)


@router.get("/certificates", operation_id="API-CERTIFICATES-LIST")
async def list_certificates(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from src.models.certificate import Certificate
    from src.models.learning import LearningTrack, LearningGoal
    result = await db.execute(
        select(Certificate)
        .join(LearningTrack, Certificate.track_id == LearningTrack.id)
        .join(LearningGoal, LearningTrack.goal_id == LearningGoal.id)
        .where(LearningGoal.user_id == current_user.id)
    )
    certs = result.scalars().all()
    return success_response(
        {"items": [{
            "id": str(c.id),
            "status": c.status.value,
            "skillName": c.skill_name,
            "issueDate": c.issue_date.isoformat() if c.issue_date else None,
            "documentNo": c.document_no,
        } for c in certs]},
        request.state.request_id,
    )