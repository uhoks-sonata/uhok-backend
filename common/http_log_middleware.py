# common/http_log_middleware.py
"""
FastAPI HTTP 로그 수집 미들웨어 (비동기)
- 요청/응답의 핵심 HTTP 컬럼들을 수집하여 로그 서비스로 전송합니다.
- 수집 컬럼: HTTP_METHOD, API_URL(라우트 패턴 우선), REQUEST_TIME, RESPONSE_TIME, RESPONSE_CODE, CLIENT_IP
- event_data(선택)는 최소 정보(쿼리/헤더 화이트리스트/성능지표)를 함께 전송합니다.
- 의존: common.log_utils.send_user_log (비동기 HTTP 전송), common.config.get_settings
- 적용: app.add_middleware(HttpLogMiddleware)

주의:
- 인증 사용자 ID는 request.state.user.user_id 가 세팅된 경우에만 추출합니다(없으면 None).
- 프록시 환경이라면 X-Forwarded-For / X-Real-IP 를 우선 사용합니다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Sequence

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from common.config import get_settings
from common.logger import get_logger
from common.log_utils import send_user_log, redact_event_data, serialize_datetime

logger = get_logger("http_log_middleware")
settings = get_settings()

# 화이트리스트 경로(로그 제외)
DEFAULT_EXCLUDE_PATHS: Sequence[str] = (
    "/health",
    "/metrics",
    "/favicon.ico",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static/",          # 정적 파일 프리픽스
    "/api/log/user/event",  # 로그 적재 API 자체는 로그 기록하지 않음
)


def _now_utc() -> datetime:
    """UTC 현재 시간을 timezone-aware datetime으로 반환

    Returns:
        datetime: tz-aware(UTC) now
    """
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    """datetime을 ISO8601 문자열로 직렬화

    Args:
        dt: tz-aware 또는 naive datetime

    Returns:
        str: ISO8601 문자열(UTC 권장)
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.astimezone(timezone.utc).isoformat()


def _should_skip_log(path: str, exclude_paths: Sequence[str]) -> bool:
    """요청 경로가 로그 제외 대상인지 판단

    Args:
        path: 요청 경로
        exclude_paths: 제외 경로(프리픽스 포함 가능)

    Returns:
        bool: 제외해야 하면 True
    """
    for p in exclude_paths:
        if p.endswith("/"):
            # 프리픽스 매칭(e.g. "/static/")
            if path.startswith(p):
                return True
        else:
            if path == p:
                return True
    return False


def _get_client_ip(request: Request) -> Optional[str]:
    """클라이언트 IP를 헤더/소켓 정보에서 추출

    우선순위:
        1) X-Forwarded-For (첫 번째)
        2) X-Real-IP
        3) request.client.host

    Args:
        request: FastAPI Request

    Returns:
        Optional[str]: IP 문자열 또는 None
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # "client, proxy1, proxy2" → 첫 값
        return xff.split(",")[0].strip()
    xrip = request.headers.get("x-real-ip")
    if xrip:
        return xrip.strip()
    return request.client.host if request.client else None


def _get_route_pattern(request: Request) -> str:
    """라우트 패턴(path_format) 또는 원본 경로를 반환

    - FastAPI 라우팅 후 request.scope['route']에 접근 가능
    - path_format이 없으면 request.url.path 사용

    Args:
        request: FastAPI Request

    Returns:
        str: 라우트 패턴 또는 경로
    """
    route = request.scope.get("route")
    if route is not None:
        # FastAPI Route는 path_format 속성이 있어 "/orders/{order_id}" 형태 제공
        path_format = getattr(route, "path_format", None)
        if path_format:
            return path_format
        path = getattr(route, "path", None)
        if path:
            return path
    return request.url.path


def _whitelist_headers(request: Request, allow: Iterable[str] = ("x-request-id", "referer", "origin")) -> Dict[str, str]:
    """헤더 중 화이트리스트 키만 추출

    Args:
        request: FastAPI Request
        allow: 허용할 헤더 키 목록(소문자 비교)

    Returns:
        Dict[str, str]: 추출된 헤더 사본
    """
    allowed = {k.lower() for k in allow}
    out: Dict[str, str] = {}
    for k, v in request.headers.items():
        if k.lower() in allowed:
            out[k] = v
    return out


def _extract_user_id(request: Request) -> Optional[int]:
    """Request 컨텍스트에서 사용자 ID를 추출

    - 인증 미들웨어/의존성에서 request.state.user 에 사용자 객체를 심어두었다고 가정
    - 없거나 형식이 다르면 None 반환

    Args:
        request: FastAPI Request

    Returns:
        Optional[int]: 사용자 ID 또는 None
    """
    user = getattr(request.state, "user", None)
    if user is None:
        return None
    # 예: services.user.models.user_model.User 와 유사하게 user_id 속성 보유
    return getattr(user, "user_id", None)


def _build_event_data_http(
    *,
    action: str,
    api_url: str,
    method: str,
    code: int,
    client_ip: Optional[str],
    request_time: datetime,
    response_time: datetime,
    query_params: Dict[str, Any],
    headers_whitelist: Dict[str, str],
    server_ms: int,
) -> Dict[str, Any]:
    """HTTP 요청/응답 기반 event_data 스냅샷을 생성

    Args:
        action: 이벤트 액션명(예: 'api_request')
        api_url: 라우트 패턴 또는 경로
        method: HTTP 메서드
        code: 응답 코드
        client_ip: 클라이언트 IP
        request_time: 요청 시작 시각(UTC 권장)
        response_time: 응답 완료 시각(UTC 권장)
        query_params: 쿼리 파라미터(dict)
        headers_whitelist: 화이트리스트 헤더(dict)
        server_ms: 처리 시간(ms)

    Returns:
        Dict[str, Any]: EVENT_DATA로 저장할 dict
    """
    return serialize_datetime({
        "schema_version": "1.0",
        "action": action,
        "request": {
            "route": api_url,
            "method": method,
            "query": query_params,
            "headers_whitelist": headers_whitelist,
            "client_ip": client_ip,
            "started_at": request_time,
        },
        "response": {
            "code": code,
            "finished_at": response_time,
        },
        "performance": {
            "server_ms": server_ms
        },
    })


class HttpLogMiddleware(BaseHTTPMiddleware):
    """HTTP 로그 수집 미들웨어

    - 요청/응답 시각을 기준으로 처리 시간을 계산하고, 핵심 HTTP 컬럼 및 event_data를 로그 서비스로 비동기 전송합니다.
    - 제외 경로는 DEFAULT_EXCLUDE_PATHS 또는 초기화 인자로 전달한 exclude_paths 를 사용합니다.

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(HttpLogMiddleware, exclude_paths=("/health", "/openapi.json"))

    Note:
        - 로그 전송은 fire-and-forget(asyncio.create_task) 방식이라 응답 지연을 유발하지 않습니다.
        - 전송 실패는 애플리케이션 흐름에 영향을 주지 않습니다(내부에서 로깅만 수행).
    """

    def __init__(
        self,
        app,
        *,
        exclude_paths: Sequence[str] = DEFAULT_EXCLUDE_PATHS,
        header_whitelist: Iterable[str] = ("x-request-id", "referer", "origin"),
        extra_sensitive_keys: Optional[Iterable[str]] = None,
        enabled: Optional[bool] = None,
    ):
        """미들웨어 초기화

        Args:
            app: ASGI 앱
            exclude_paths: 로그 제외 경로 목록
            header_whitelist: event_data에 포함할 헤더 키(소문자 비교)
            extra_sensitive_keys: event_data 마스킹에 사용할 추가 민감 키 목록
            enabled: 강제 on/off. None이면 환경설정(settings.enable_http_log 등)을 따름
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths
        self.header_whitelist = tuple(header_whitelist)
        self.extra_sensitive_keys = set(extra_sensitive_keys or [])
        # 환경 변수(.env)로 제어(없으면 기본 True)
        self.enabled = enabled if enabled is not None else bool(getattr(settings, "enable_http_log", True))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """요청을 가로채 핵심 HTTP 데이터를 수집하고 응답 이후 비동기 전송

        - 요청 시작/종료 시각을 측정하여 처리 시간(ms) 계산
        - 라우트 패턴(API_URL), 메서드, 응답 코드, 클라이언트 IP 수집
        - event_data(쿼리/헤더 일부/성능지표) 포함하여 전송

        Args:
            request: FastAPI Request
            call_next: 다음 ASGI 처리자

        Returns:
            Response: 원래의 응답
        """
        # 비활성 또는 제외 경로는 패스
        if not self.enabled or _should_skip_log(request.url.path, self.exclude_paths):
            return await call_next(request)

        # 요청 시각
        started_at = _now_utc()

        # 핵심 컬럼 수집 (요청 시작 시점)
        method = request.method
        api_url = _get_route_pattern(request)
        client_ip = _get_client_ip(request)

        # HTTP 정보를 request.state에 미리 저장 (라우터에서 사용 가능)
        request.state.http_info = {
            "http_method": method,
            "api_url": api_url,
            "request_time": started_at,
            "response_time": None,  # 나중에 업데이트
            "response_code": None,  # 나중에 업데이트
            "client_ip": client_ip
        }

        # 응답 처리(+예외 처리)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = getattr(response, "status_code", 200) or 200
        except Exception:
            # 예외 발생도 로깅 대상(500)
            logger.exception("요청 처리 중 예외 발생(HTTP 로그 수집)", extra={"path": request.url.path})
            status_code = 500
            raise
        finally:
            finished_at = _now_utc()
            server_ms = int((finished_at - started_at).total_seconds() * 1000)

            # user_id 추출(없으면 None)
            user_id = _extract_user_id(request)
            
            # HTTP 정보 업데이트 (응답 완료 후)
            request.state.http_info.update({
                "response_time": finished_at,
                "response_code": status_code
            })

            # event_data(민감키 마스킹 포함) 준비
            # 쿼리 파라미터(dict) — 토큰류는 민감키로 마스킹 가능
            query_params: Dict[str, Any] = dict(request.query_params)
            headers_wl = _whitelist_headers(request, self.header_whitelist)

            raw_event = _build_event_data_http(
                action="api_request",
                api_url=api_url,
                method=method,
                code=status_code,
                client_ip=client_ip,
                request_time=started_at,
                response_time=finished_at,
                query_params=query_params,
                headers_whitelist=headers_wl,
                server_ms=server_ms,
            )

            # 추가 민감 키 마스킹(예: "phone", "email" 등)
            event_data = redact_event_data(raw_event, self.extra_sensitive_keys)

            # 비동기 전송(fire-and-forget) - HTTP 정보 포함
            asyncio.create_task(
                send_user_log(
                    user_id=user_id or 0,  # 익명은 0 등으로 보낼 수 있음(수신측에서 None 처리 가능)
                    event_type="api_request",
                    event_data=event_data,
                    # HTTP 정보 추가
                    http_method=method,
                    api_url=api_url,
                    request_time=started_at,
                    response_time=finished_at,
                    response_code=status_code,
                    client_ip=client_ip,
                    extra_sensitive_keys=self.extra_sensitive_keys,
                    # 필요 시 헤더 추가 가능(코릴레이션/트레이스ID 등)
                    extra_headers={"X-Request-Path": api_url},
                )
            )

        return response
