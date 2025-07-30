# errors.py
"""
공통 에러 타입 정의
"""
from fastapi import HTTPException, status

class NotAuthenticatedException(HTTPException):
    """401 에러 - 인증 실패"""
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")

class NotFoundException(HTTPException):
    """404 에러 - 항목 없음"""
    def __init__(self, name: str = "데이터"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"{name}을(를) 찾을 수 없습니다.")
