"""
HTTP 정보 수집을 위한 공통 의존성 함수들
- 모든 라우터에서 HTTP 정보를 일관성 있게 수집할 수 있도록 제공
"""
from fastapi import Request
from datetime import datetime, timezone
from common.logger import get_logger

logger = get_logger("http_dependencies")

def extract_http_info(request: Request, response_code: int = 200) -> dict:
    """
    request.state에서 HTTP 정보를 추출하여 로그 데이터에 추가
    
    Args:
        request: FastAPI Request 객체
        response_code: HTTP 응답 코드 (기본값: 200)
    
    Returns:
        dict: HTTP 정보가 포함된 딕셔너리
    """
    http_info = {}
    
    # 미들웨어에서 저장한 HTTP 정보가 있는지 확인
    if hasattr(request.state, 'http_info') and request.state.http_info:
        http_info = request.state.http_info.copy()
        # response_time과 response_code를 현재 값으로 업데이트
        http_info["response_time"] = datetime.now(timezone.utc)
        http_info["response_code"] = response_code
        logger.debug(f"HTTP 정보 추출 (업데이트됨): {http_info}")
    else:
        # 미들웨어 정보가 없으면 기본값으로 설정
        http_info = {
            "http_method": request.method,
            "api_url": str(request.url),
            "request_time": None,
            "response_time": datetime.now(timezone.utc),
            "response_code": response_code,
            "client_ip": request.client.host if request.client else None
        }
        logger.debug(f"기본 HTTP 정보 설정: {http_info}")
    
    return http_info

def get_http_info_for_logging(request: Request, response_code: int = 200) -> dict:
    """
    로깅용 HTTP 정보를 반환하는 의존성 함수
    
    Args:
        request: FastAPI Request 객체
        response_code: HTTP 응답 코드
    
    Returns:
        dict: 로깅에 사용할 HTTP 정보
    """
    return extract_http_info(request, response_code)
