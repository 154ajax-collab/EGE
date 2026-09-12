from datetime import datetime, timezone
import uuid
import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import AppError, ErrorCode
from src.models.certificate import Certificate, CertificateStatus
from src.models.exam import ExamAttempt, Exam, AttemptStatus
from src.models.learning import LearningTrack, LearningGoal
from src.models.user import User, Profile
from src.repositories.user_repository import UserRepository
from src.adapters.renderer_adapter import RendererAdapter


class CertificateService:
    """Раздел 6.8 ТЗ"""
    
    def __init__(self, db: AsyncSession, renderer: RendererAdapter):
        self.db = db
        self.renderer = renderer
        self.user_repo = UserRepository(db)
    
    async def generate_certificate(self, track_id: uuid.UUID, user_id: uuid.UUID,
                                    final_attempt_id: str, profile_version: int,
                                    template_version: str, legal_text_version: str) -> Certificate:
        """FN-DIPLOMA-GENERATE"""
        # Проверка трека
        track_result = await self.db.execute(
            select(LearningTrack).join(LearningGoal).where(
                LearningTrack.id == track_id,
                LearningGoal.user_id == user_id,
            )
        )
        track = track_result.scalar_one_or_none()
        if not track:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Трек не найден", 404)
        
        # Проверка final attempt
        attempt_result = await self.db.execute(
            select(ExamAttempt).join(Exam).where(
                ExamAttempt.id == uuid.UUID(final_attempt_id),
                Exam.track_id == track.id,
            )
        )
        attempt = attempt_result.scalar_one_or_none()
        if not attempt or attempt.status != AttemptStatus.PASSED:
            raise AppError(
                code=ErrorCode.BUSINESS_RULE_VIOLATION,
                message="Финальный экзамен не сдан",
                status_code=422,
            )
        
        # Профиль
        profile = await self.user_repo.get_profile(user_id)
        if not profile or not profile.certificate_name:
            raise AppError(
                code=ErrorCode.BUSINESS_RULE_VIOLATION,
                message="Не указано имя для сертификата",
                status_code=422,
            )
        
        # Проверяем — может, уже выпущен
        existing_result = await self.db.execute(
            select(Certificate).where(Certificate.track_id == track.id)
        )
        existing = existing_result.scalar_one_or_none()
        if existing and existing.status == CertificateStatus.ISSUED:
            return existing
        
        # Создаем
        doc_no = self._generate_document_no()
        cert = Certificate(
            track_id=track.id,
            certificate_name=profile.certificate_name,
            skill_name=track.title,
            issue_date=None,
            document_no=doc_no,
            template_version=template_version,
            legal_text_version=legal_text_version,
            status=CertificateStatus.GENERATING,
        )
        self.db.add(cert)
        await self.db.commit()
        
        # Рендеринг
        try:
            storage_key = await self.renderer.render_certificate({
                "certificateId": str(cert.id),
                "certificateName": profile.certificate_name,
                "skillName": track.title,
                "documentNo": doc_no,
            })
            cert.storage_key = storage_key
            cert.issue_date = datetime.now(timezone.utc)
            cert.status = CertificateStatus.ISSUED
        except Exception:
            cert.status = CertificateStatus.FAILED
        
        await self.db.commit()
        return cert
    
    async def get_certificate(self, cert_id: uuid.UUID, user_id: uuid.UUID) -> Certificate:
        """FN-DIPLOMA-STATUS"""
        result = await self.db.execute(
            select(Certificate)
            .join(LearningTrack, Certificate.track_id == LearningTrack.id)
            .join(LearningGoal, LearningTrack.goal_id == LearningGoal.id)
            .where(Certificate.id == cert_id, LearningGoal.user_id == user_id)
        )
        cert = result.scalar_one_or_none()
        if not cert:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Сертификат не найден", 404)
        return cert
    
    async def create_download_link(self, cert_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        """FN-DIPLOMA-DOWNLOAD"""
        cert = await self.get_certificate(cert_id, user_id)
        if cert.status != CertificateStatus.ISSUED:
            raise AppError(
                code=ErrorCode.STATE_CONFLICT,
                message="Сертификат ещё не готов",
                status_code=409,
            )
        
        # Mock signed URL (в prod — S3 presigned URL)
        expires_at = datetime.now(timezone.utc)
        from datetime import timedelta
        expires_at = expires_at + timedelta(seconds=settings.DOWNLOAD_LINK_TTL)
        
        return {
            "url": f"https://storage.repetit.center/{cert.storage_key}?signed=mock",
            "expiresAt": expires_at.isoformat(),
            "filename": f"certificate-{cert.document_no}.png",
            "contentType": "image/png",
            "sizeBytes": None,
        }
    
    def _generate_document_no(self) -> str:
        # Формат: RC-YYYY-XXXXXX
        year = datetime.now(timezone.utc).year
        suffix = ''.join(secrets.choice(string.digits) for _ in range(6))
        return f"RC-{year}-{suffix}"