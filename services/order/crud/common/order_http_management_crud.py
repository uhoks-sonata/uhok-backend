"""Order HTTP utility management CRUD functions."""

from __future__ import annotations

from typing import Dict, Any

import httpx

from common.logger import get_logger

logger = get_logger("order_crud")

async def _post_json(url: str, json: Dict[str, Any], timeout: float = 20.0) -> httpx.Response:
    """
    비동기 HTTP POST 유틸
    
    Args:
        url: 요청할 URL
        json: POST할 JSON 데이터
        timeout: 연결/읽기 통합 타임아웃(초, 기본값: 20.0)
    
    Returns:
        httpx.Response: HTTP 응답 객체
        
    Note:
        - httpx.AsyncClient를 context manager로 생성하여 커넥션 누수 방지
        - Content-Type: application/json 헤더 자동 설정
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=json, headers={"Content-Type": "application/json"})


async def _get_json(url: str, timeout: float = 15.0) -> httpx.Response:
    """
    비동기 HTTP GET 유틸
    
    Args:
        url: 요청할 URL
        timeout: 연결/읽기 통합 타임아웃(초, 기본값: 15.0)
    
    Returns:
        httpx.Response: HTTP 응답 객체
        
    Note:
        - httpx.AsyncClient 사용
        - 상세한 로깅을 통한 디버깅 지원
        - 예외 발생 시 에러 타입과 함께 로깅
    """
    # logger.info(f"HTTP GET 요청 시작: url={url}, timeout={timeout}초")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
    # logger.info(f"httpx.AsyncClient 생성 완료, GET 요청 전송: {url}")
            response = await client.get(url)
    # logger.info(f"HTTP GET 응답 수신: url={url}, status_code={response.status_code}")
            return response
    except Exception as e:
        logger.error(f"HTTP GET 요청 실패: url={url}, error={str(e)}, error_type={type(e).__name__}")
        raise


