# common/log_utils.py
from __future__ import annotations

import json
import random
import asyncio
from typing import Any, Dict, Iterable, Optional
from datetime import datetime, timezone

import anyio
import httpx

from common.logger import get_logger

logger = get_logger("log_utils")

# 로그 전송 불필요하므로 API_URL 제거
API_URL = None  # 사용하지 않음
AUTH_TOKEN = None  # 사용하지 않음

SENSITIVE_KEYS: set[str] = {
    "password", "pwd", "pass",
    "authorization", "cookie", "set-cookie",
    "access_token", "refresh_token", "id_token", "token", "secret",
    "card_number", "cvc", "cvv", "ssn", "resident_id",
    "jumin", "bank_account", "account_no",
}

def serialize_datetime(obj: Any) -> Any:
    """
    datetime, dict, list 내부의 datetime을 ISO8601 문자열로 변환
    """
    if isinstance(obj, datetime):
        return obj.astimezone(timezone.utc).isoformat() if obj.tzinfo else obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_datetime(v) for v in obj]
    return obj

def _redact_value(_: Any) -> str:
    """민감 값 마스킹 문자열 반환"""
    return "***REDACTED***"

def redact_event_data(
    data: Optional[Dict[str, Any]],
    extra_sensitive_keys: Optional[Iterable[str]] = None
) -> Dict[str, Any]:
    """
    event_data 내 민감 키(토큰/비번 등)를 재귀적으로 마스킹한 사본 반환
    """
    sensitive = {k.lower() for k in (extra_sensitive_keys or [])} | {k.lower() for k in SENSITIVE_KEYS}
    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                out[k] = _redact_value(v) if k.lower() in sensitive else walk(v)
            return out
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        return obj
    return walk(dict(data or {}))

def _build_headers(extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    전송용 헤더 구성(Authorization 포함 가능)
    """
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    if extra_headers:
        headers.update(extra_headers)
    return headers

def _summarize_payload(payload: Dict[str, Any]) -> str:
    """
    디버그용: 주요 키/크기만 요약 문자열로 반환
    """
    try:
        raw = json.dumps(payload, ensure_ascii=False)
        size = len(raw.encode("utf-8"))
        keys = list(payload.keys())
        return f"keys={keys}, size_bytes={size}"
    except Exception:
        return f"keys={list(payload.keys())}"

async def _log_http_error(resp: httpx.Response, payload: Dict[str, Any]) -> None:
    """
    4xx/5xx 응답일 때 서버가 준 바디/헤더/요약 페이로드를 에러로 남김
    """
    body_preview = ""
    try:
        # JSON이면 pretty, 아니면 text 앞부분만
        if "application/json" in (resp.headers.get("content-type") or ""):
            body_preview = json.dumps(resp.json(), ensure_ascii=False)[:2000]
        else:
            body_preview = (resp.text or "")[:2000]
    except Exception:
        body_preview = "<body parse failed>"

    logger.error(
        "[log_utils] Log API error: status=%s, url=%s, resp_body=%s, payload_summary=%s",
        resp.status_code, str(resp.request.url), body_preview, _summarize_payload(payload)
    )

async def check_log_service_health(timeout: float = 2.0) -> bool:
    """
    로그 서비스 헬스체크(API_URL이 없으면 False 반환)
    """
    if not API_URL:
        return False
    
    base = API_URL.rstrip("/")
    url = f"{base}/health"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return 200 <= r.status_code < 300
    except Exception:
        return False

async def send_user_log(
    user_id: int,
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None,
    *,
    # ⬇️ 추가: 서버가 상위 필드로 받길 원할 경우를 대비해 포함
    http_method: Optional[str] = None,
    api_url: Optional[str] = None,
    request_time: Optional[datetime] = None,
    response_time: Optional[datetime] = None,
    response_code: Optional[int] = None,
    client_ip: Optional[str] = None,
    # 재시도/타임아웃
    max_retries: int = 2,
    base_timeout: float = 5.0,
    # 기타
    extra_sensitive_keys: Optional[Iterable[str]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    raise_on_4xx: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    사용자 로그를 직접 DB에 저장(비동기)
    - HTTP 전송 대신 직접 PostgreSQL 로그 DB에 저장
    - HTTP 정보를 포함하여 저장
    """
    
    # 직접 DB에 저장하도록 변경 (재시도 로직 포함)
    max_retries = 2
    for attempt in range(max_retries):
        try:
            from common.database.postgres_log import SessionLocal
            from services.log.crud.user_event_log_crud import create_user_log
            
            # 로그 데이터 구성
            log_data = {
                "user_id": user_id,
                "event_type": event_type,
                "event_data": event_data,
                "http_method": http_method,
                "api_url": api_url,
                "request_time": request_time,
                "response_time": response_time,
                "response_code": response_code,
                "client_ip": client_ip
            }
            
            # 로그 DB 세션 생성 및 저장
            async with SessionLocal() as db:
                log_obj = await create_user_log(db, log_data)
                logger.debug(f"[log_utils] 로그 DB 저장 완료: user_id={user_id}, event_type={event_type}, log_id={log_obj.log_id}")
                return {"log_id": log_obj.log_id, "status": "saved_to_db"}
                
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"[log_utils] 로그 DB 저장 재시도 {attempt + 1}/{max_retries}: user_id={user_id}, error={str(e)}")
                await asyncio.sleep(0.5)  # 0.5초 대기 후 재시도
                continue
            else:
                logger.error(f"[log_utils] 로그 DB 저장 최종 실패: user_id={user_id}, event_type={event_type}, error={str(e)}")
                # 로그 저장 실패는 전체 프로세스를 중단하지 않도록 None 반환
                return None
