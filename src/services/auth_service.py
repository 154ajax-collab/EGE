from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import uuid
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.exceptions import AppError, ErrorCode
from src.core.security import (
    hash_password, verify_password, generate_token, hash_token
)
from src.models.user import User, Profile, AuthStatus
from src.models.auth import OneTimeToken, TokenType, Session
from src.repositories.user_repository import UserRepository
from src.adapters.email_adapter import EmailAdapter

logger = structlog.get_logger()


class AuthService:
    """Сервис авторизации (раздел 6.1 ТЗ)"""
    
    def __init__(self, db: AsyncSession, email_adapter: EmailAdapter):
        self.db = db
        self.email_adapter = email_adapter
        self.user_repo = UserRepository(db)
    
    # === FN-AUTH-SIGNUP ===
    async def register(
        self,
        display_name: str,
        email: str,
        password: str,
        consent: dict,
    ) -> Tuple[User, Profile]:
        """
        FN-AUTH-SIGNUP: Зарегистрировать пользователя
        """
        # 1. Нормализация email
        normalized_email = email.lower().strip()
        
        # 2. Проверка уникальности
        existing = await self.user_repo.get_by_email(normalized_email)
        if existing:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Email уже используется",
                status_code=400,
                field_errors=[{
                    "field": "email",
                    "code": "EMAIL_ALREADY_USED",
                    "message": "Этот email уже зарегистрирован"
                }]
            )
        
        # 3. Хеширование пароля
        password_hash = hash_password(password)
        
        # 4. Создание User и Profile
        user = await self.user_repo.create(normalized_email, password_hash)
        profile = await self.user_repo.create_profile(user.id, display_name)
        
        # 5. Создание verification token
        token = generate_token()
        token_hash = hash_token(token)
        
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.VERIFICATION_TOKEN_TTL
        )
        
        verification_token = OneTimeToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type=TokenType.EMAIL_VERIFICATION,
            expires_at=expires_at,
        )
        self.db.add(verification_token)
        
        # 6. Коммит транзакции
        await self.db.commit()
        
        # 7. Отправка email (после коммита, чтобы не откатывать при ошибке)
        try:
            await self.email_adapter.send_verification_email(normalized_email, token)
        except Exception as e:
            logger.error("Failed to send verification email", error=str(e), user_id=str(user.id))
            # Не откатываем регистрацию, пользователь сможет запросить письмо повторно
        
        logger.info("User registered", user_id=str(user.id), email=normalized_email)
        
        return user, profile
    
    # === FN-AUTH-LOGIN ===
    async def login(
        self,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, Profile, str, str]:
        """
        FN-AUTH-LOGIN: Войти в систему
        Возвращает (user, profile, session_token, csrf_token)
        """
        normalized_email = email.lower().strip()
        
        # 1. Поиск пользователя
        user = await self.user_repo.get_by_email(normalized_email)
        
        # 2. Одинаковый ответ при неизвестном email и неверном пароле
        if not user or not verify_password(password, user.password_hash):
            raise AppError(
                code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Неверный email или пароль",
                status_code=401,
                retryable=False,
            )
        
        # 3. Проверка статуса
        if user.auth_status == AuthStatus.PENDING:
            raise AppError(
                code=ErrorCode.EMAIL_NOT_VERIFIED,
                message="Email не подтвержден. Проверьте почту.",
                status_code=401,
            )
        
        if user.auth_status == AuthStatus.LOCKED:
            raise AppError(
                code=ErrorCode.ACCOUNT_LOCKED,
                message="Аккаунт заблокирован",
                status_code=401,
            )
        
        if user.auth_status == AuthStatus.DELETION_PENDING:
            raise AppError(
                code=ErrorCode.ACCESS_DENIED,
                message="Аккаунт находится в процессе удаления",
                status_code=403,
            )
        
        # 4. Создание сессии
        session_token = generate_token(48)
        csrf_token = generate_token(24)
        
        session = Session(
            user_id=user.id,
            token_hash=hash_token(session_token),
            csrf_token=csrf_token,
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=settings.SESSION_MAX_AGE
            ),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(session)
        
        user.last_login_at = datetime.now(timezone.utc)
        """
        FN-AUTH-RESTORE: Запросить восстановление пароля
        Всегда возвращает одинаковый ответ (не раскрываем наличие аккаунта)
        """
        normalized_email = email.lower().strip()
        user = await self.user_repo.get_by_email(normalized_email)
        
        # Если пользователь не найден или не активен — просто выходим
        if not user or user.auth_status != AuthStatus.ACTIVE:
            logger.info("Password restore requested for non-existent/inactive user")
            return
        
        # Создаем токен
        token = generate_token()
        token_hash = hash_token(token)
        
        reset_token = OneTimeToken(
            user_id=user.id,
            token_hash=token_hash,
            token_type=TokenType.PASSWORD_RESET,
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=settings.RESET_TOKEN_TTL
            ),
        )
        self.db.add(reset_token)
        await self.db.commit()
        
                OneTimeToken.token_hash == token_hash,
                OneTimeToken.token_type == TokenType.PASSWORD_RESET,
            )
        )
        reset_token = result.scalar_one_or_none()
        
        if not reset_token:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Недействительный токен",
                status_code=400,
                field_errors=[{
                    "field": "token",
                    "code": "RESET_TOKEN_INVALID",
                    "message": "Ссылка недействительна"
                }]
            )
        
        # 2. Проверка TTL
        if reset_token.expires_at < datetime.now(timezone.utc):
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Токен истек",
                status_code=400,
                field_errors=[{
                    "field": "token",
                    "code": "RESET_TOKEN_EXPIRED",
                    "message": "Ссылка устарела. Запросите новую."
                }]
            )
        
        # 3. Проверка single use
        if reset_token.used_at is not None:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Токен уже использован",
                status_code=400,
                field_errors=[{
                    "field": "token",
                    "code": "RESET_TOKEN_INVALID",
                    "message": "Ссылка уже была использована"
                }]
            )
        
        # 4. Обновление пароля
        user = await self.user_repo.get_by_id(reset_token.user_id)
        if not user:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Пользователь не найден",
                status_code=404,
            )
        
        user.password_hash = hash_password(new_password)
        reset_token.used_at = datetime.now(timezone.utc)
        
        # 5. Отзыв всех сессий
        await self._revoke_all_sessions(user.id)
        
        await self.db.commit()
        logger.info("Password reset completed", user_id=str(user.id))
    
    # === FN-AUTH-VERIFY ===
    async def verify_email(self, token: str) -> Tuple[User, Profile]:
        """
        FN-AUTH-VERIFY: Подтвердить email
        """
        token_hash = hash_token(token)
        
        # 1. Поиск токена
        result = await self.db.execute(
            select(OneTimeToken).where(
                OneTimeToken.token_hash == token_hash,
                OneTimeToken.token_type == TokenType.EMAIL_VERIFICATION,
            )
        )
        verification_token = result.scalar_one_or_none()
        
        if not verification_token:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Недействительный токен",
                status_code=400,
                field_errors=[{
                    "field": "token",
                    "code": "VERIFICATION_TOKEN_INVALID",
                    "message": "Ссылка недействительна"
                }]
            )
        
        # 2. Проверка TTL
        if verification_token.expires_at < datetime.now(timezone.utc):
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Токен истек",
                status_code=400,
                field_errors=[{
                    "field": "token",
                    "code": "VERIFICATION_TOKEN_EXPIRED",
                    "message": "Ссылка устарела"
                }]
            )
        
        # 3. Получение пользователя
        user = await self.user_repo.get_by_id(verification_token.user_id)
        if not user:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Пользователь не найден",
                status_code=404,
            )
        
        # 4. Idempotent результат для уже подтвержденного
        if user.auth_status == AuthStatus.ACTIVE:
            profile = await self.user_repo.get_profile(user.id)
            return user, profile
        
        # 5. Активация
        user.auth_status = AuthStatus.ACTIVE
        user.email_verified_at = datetime.now(timezone.utc)
        verification_token.used_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        profile = await self.user_repo.get_profile(user.id)
        logger.info("Email verified", user_id=str(user.id))
        
        return user, profile
    
    # === FN-AUTH-LOGOUT ===
    async def logout(self, session_token: str, user_id: uuid.UUID, all_sessions: bool = False) -> None:
        """
        FN-AUTH-LOGOUT: Выйти из системы
        """
        if all_sessions:
            await self._revoke_all_sessions(user_id)
        else:
            # Отзываем только текущую сессию
            token_hash = hash_token(session_token)
            result = await self.db.execute(
                select(Session).where(Session.token_hash == token_hash)
            )
            session = result.scalar_one_or_none()
            if session:
                session.revoked_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        logger.info("User logged out", user_id=str(user_id), all_sessions=all_sessions)
    
    # === Вспомогательные методы ===
    
    async def _revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        """Отзыв всех сессий пользователя"""
        result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
            )
        )
        sessions = result.scalars().all()
        now = datetime.now(timezone.utc)
        for session in sessions:
            session.revoked_at = now
    
    async def get_session(self, session_token: str) -> Optional[Tuple[User, Session]]:
        """Получение активной сессии по токену"""
        token_hash = hash_token(session_token)
        result = await self.db.execute(
            select(Session).where(
                Session.token_hash == token_hash,
                Session.revoked_at.is_(None),
                Session.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        
        user = await self.user_repo.get_by_id(session.user_id)
        if not user:
            return None
        
        return user, session        # Отправляем email
        try:
            select(OneTimeToken).where(
            await self.email_adapter.send_password_reset_email(normalized_email, token)
        except Exception as e:
        result = await self.db.execute(
        token_hash = hash_token(token)
        
        # 1. Поиск токена
            logger.error("Failed to send reset email", error=str(e))
        
        logger.info("Password restore requested", user_id=str(user.id))
    
    # === FN-AUTH-RESET ===
        """
    async def reset_password(self, token: str, new_password: str) -> None:
        """
        FN-AUTH-RESET: Установить новый пароль по одноразовой ссылке
    
    # === FN-AUTH-RESTORE ===
    async def request_password_restore(self, email: str) -> None:
        logger.info("User logged in", user_id=str(user.id))
        
        return user, profile, session_token, csrf_token
        # 6. Получаем профиль
        profile = await self.user_repo.get_profile(user.id)
        
        
        await self.db.commit()
        

