"""
Custom exceptions for the application.
"""
from typing import Any, Optional
from fastapi import HTTPException, status


class VoiceconException(Exception):
    """Base exception for Voicecon application."""
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(VoiceconException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(VoiceconException):
    """Raised when user lacks required permissions."""
    pass


class ResourceNotFoundError(VoiceconException):
    """Raised when a requested resource is not found."""
    pass


class ResourceAlreadyExistsError(VoiceconException):
    """Raised when attempting to create a resource that already exists."""
    pass


class ValidationError(VoiceconException):
    """Raised when data validation fails."""
    pass


class IntegrationError(VoiceconException):
    """Raised when external integration fails."""
    pass


class WorkflowExecutionError(VoiceconException):
    """Raised when workflow execution fails."""
    pass


class CallError(VoiceconException):
    """Raised when call-related operations fail."""
    pass


class RateLimitError(VoiceconException):
    """Raised when rate limit is exceeded."""
    pass


class QuotaExceededError(VoiceconException):
    """Raised when usage quota is exceeded."""
    pass


# HTTP Exception helpers
def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def not_found_exception(resource: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found",
    )


def forbidden_exception(message: str = "Forbidden") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message,
    )


def bad_request_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )


def conflict_exception(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message,
    )
