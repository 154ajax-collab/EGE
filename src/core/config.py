from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # Общие
    APP_NAME: str = "Репит.центр"
    APP_VERSION: str = "1.1"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # База данных
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/repetit"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Безопасность
    SECRET_KEY: str
    COOKIE_SECURE: bool = False
    COOKIE_HTTPONLY: bool = True
    COOKIE_SAMESITE: str = "lax"
    SESSION_MAX_AGE: int = 604800  # 7 дней

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Rate limits
    RATE_LIMIT_AUTH: int = 5
    RATE_LIMIT_AI: int = 10

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@repetit.center"

    # AI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    # S3
    S3_ENDPOINT: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_BUCKET_CERTIFICATES: str = "certificates"

    # Job settings
    JOB_TIMEOUT: int = 300

    # TTL для токенов
    VERIFICATION_TOKEN_TTL: int = 86400  # 24 часа
    RESET_TOKEN_TTL: int = 3600  # 1 час
    DOWNLOAD_LINK_TTL: int = 300  # 5 минут

    # Экзамен
    EXAM_PASSING_PERCENT: int = 80

    # Удаление аккаунта
    DELETION_GRACE_PERIOD_DAYS: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()