from enum import Enum


class ErrorCode(str, Enum):
    # 400
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # 401
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"

    # 403
    ACCESS_DENIED = "ACCESS_DENIED"
    PREREQUISITE_LOCKED = "PREREQUISITE_LOCKED"

    # 404
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"

    # 409
    VERSION_CONFLICT = "VERSION_CONFLICT"
    STATE_CONFLICT = "STATE_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"

    # 422
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"

    # 429
    RATE_LIMITED = "RATE_LIMITED"

    # 502/503
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"


class AppError(Exception):
    def __init__(
            self,
            code: ErrorCode,
            message: str,
            status_code: int,
            field_errors: list = None,
            details: dict = None,
            retryable: bool = False
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field_errors = field_errors or []
        self.details = details or {}
        self.retryable = retryable
        super().__init__(message)