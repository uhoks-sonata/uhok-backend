"""
공통 에러 타입 정의 모듈
- FastAPI 기반 프로젝트에서 자주 사용하는 에러 클래스 정의
"""

from fastapi import HTTPException, status
from common.logger import get_logger

logger = get_logger("errors")


class BadRequestException(HTTPException):
    """400 Bad Request - 요청 파라미터 오류 등"""
    def __init__(self, message: str = "잘못된 요청입니다."):
        logger.warning(f"BadRequestException raised: {message}")
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )


class NotAuthenticatedException(HTTPException):
    """401 Unauthorized - 인증 실패 (JWT 없음 또는 무효)"""
    def __init__(self):
        logger.warning("NotAuthenticatedException raised: Authentication required")
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다. 로그인 후 다시 시도해주세요."
        )


class TokenExpiredException(HTTPException):
    """401 Unauthorized - 토큰 만료"""
    def __init__(self):
        logger.warning("TokenExpiredException raised: Token expired")
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다. 다시 로그인해주세요."
        )


class InvalidTokenException(HTTPException):
    """401 Unauthorized - 토큰이 변조되었거나 형식이 올바르지 않음"""
    def __init__(self, message: str = "유효하지 않은 토큰입니다."):
        logger.warning(f"InvalidTokenException raised: {message}")
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message
        )


class NotAuthorizedException(HTTPException):
    """403 Forbidden - 인가 실패 (권한 부족)"""
    def __init__(self, action: str = "해당 작업"):
        logger.warning(f"NotAuthorizedException raised: Insufficient permission for {action}")
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{action}을(를) 수행할 권한이 없습니다."
        )


class NotFoundException(HTTPException):
    """404 Not Found - 데이터 없음"""
    def __init__(self, name: str = "데이터"):
        logger.warning(f"NotFoundException raised: {name} not found")
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name}을(를) 찾을 수 없습니다."
        )


class ConflictException(HTTPException):
    """409 Conflict - 데이터 충돌 (중복된 리소스 등)"""
    def __init__(self, message: str = "이미 존재하는 항목입니다."):
        logger.warning(f"ConflictException raised: {message}")
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=message
        )


class UnprocessableEntityException(HTTPException):
    """422 Unprocessable Entity - 유효성 검증 실패 등"""
    def __init__(self, message: str = "요청을 처리할 수 없습니다. 입력값을 확인해주세요."):
        logger.warning(f"UnprocessableEntityException raised: {message}")
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=message
        )


class RateLimitExceededException(HTTPException):
    """429 Too Many Requests - 요청 한도 초과"""
    def __init__(self, retry_after: int = 60):
        logger.warning(f"RateLimitExceededException raised: Rate limit exceeded, retry after {retry_after}s")
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"요청이 너무 많습니다. {retry_after}초 후에 다시 시도해주세요."
        )


class InternalServerErrorException(HTTPException):
    """500 Internal Server Error - 서버 오류"""
    def __init__(self, message: str = "서버 내부 오류가 발생했습니다."):
        logger.error(f"InternalServerErrorException raised: {message}")
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )


class ServiceUnavailableException(HTTPException):
    """503 Service Unavailable - 외부 서비스 연동 실패 등"""
    def __init__(self, message: str = "현재 서비스를 이용할 수 없습니다. 잠시 후 다시 시도해주세요."):
        logger.error(f"ServiceUnavailableException raised: {message}")
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message
        )
