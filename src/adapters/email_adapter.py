from abc import ABC, abstractmethod
from typing import Optional
import structlog

from src.core.config import settings

logger = structlog.get_logger()


class EmailAdapter(ABC):
    """Базовый интерфейс для email адаптера (раздел 8 ТЗ)"""

    @abstractmethod
    async def send_verification_email(self, to_email: str, token: str) -> None:
        """Отправка письма с подтверждением email"""
        pass

    @abstractmethod
    async def send_password_reset_email(self, to_email: str, token: str) -> None:
        """Отправка письма для сброса пароля"""
        pass

    @abstractmethod
    async def send_deletion_confirmation_email(self, to_email: str) -> None:
        """Отправка письма об удалении аккаунта"""
        pass


class MockEmailAdapter(EmailAdapter):
    """Mock адаптер для разработки (раздел 12 ТЗ)"""

    async def send_verification_email(self, to_email: str, token: str) -> None:
        logger.info(
            "MOCK: Verification email",
            to_email=to_email,
            token=token[:8] + "...",  # Не логируем токен целиком
            verify_url=f"/verify?token={token}"
        )

    async def send_password_reset_email(self, to_email: str, token: str) -> None:
        logger.info(
            "MOCK: Password reset email",
            to_email=to_email,
            token=token[:8] + "...",
            reset_url=f"/reset?token={token}"
        )

    async def send_deletion_confirmation_email(self, to_email: str) -> None:
        logger.info("MOCK: Deletion confirmation email", to_email=to_email)


class SMTPEmailAdapter(EmailAdapter):
    """Реальный SMTP адаптер"""

    async def send_verification_email(self, to_email: str, token: str) -> None:
        # TODO: Реализовать через aiosmtplib или httpx к email-провайдеру
        logger.info("Sending verification email", to_email=to_email)
        raise NotImplementedError("SMTP adapter not implemented yet")

    async def send_password_reset_email(self, to_email: str, token: str) -> None:
        raise NotImplementedError("SMTP adapter not implemented yet")

    async def send_deletion_confirmation_email(self, to_email: str) -> None:
        raise NotImplementedError("SMTP adapter not implemented yet")


def get_email_adapter() -> EmailAdapter:
    """Фабрика для получения адаптера"""
    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        return SMTPEmailAdapter()
    return MockEmailAdapter()