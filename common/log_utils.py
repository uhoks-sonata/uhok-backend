"""
BackgroundTasks용 로그 API 호출 함수 (.env config 사용)
"""
import requests
import json
from datetime import datetime
from common.config import get_settings
from common.logger import get_logger

settings = get_settings()
logger = get_logger("log_utils")
api_url = settings.log_api_url   # .env에서 불러옴


def serialize_datetime(obj):
    """
    datetime 객체를 JSON 직렬화 가능한 형태로 변환
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    else:
        return obj

def check_log_service_health():
    """
    로그 서비스 상태 확인 (선택적)
    """
    try:
        # 헬스체크 엔드포인트가 있다면 사용
        health_url = api_url.replace('/user-event-log', '/user-event-log/health')
        response = requests.get(health_url, timeout=3)  # 3초로 단축
        if response.status_code == 200:
            logger.debug("로그 서비스 헬스체크 성공")
            return True
        else:
            logger.debug(f"로그 서비스 헬스체크 실패: {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        logger.debug("로그 서비스 헬스체크 타임아웃")
        return False
    except requests.exceptions.ConnectionError:
        logger.debug("로그 서비스 헬스체크 연결 실패")
        return False
    except Exception:
        logger.debug("로그 서비스 헬스체크 예외 발생")
        return False

def send_user_log(user_id: int, event_type: str, event_data: dict = None):
    """
    사용자 행동 로그를 로그 서비스로 전송 (BackgroundTasks)
    """
    # 헬스체크는 선택적으로 수행 (실패해도 로그 전송 시도)
    health_check_passed = check_log_service_health()
    if not health_check_passed:
        logger.debug(f"로그 서비스 헬스체크 실패했지만 로그 전송을 시도합니다: user_id={user_id}, event_type={event_type}")
    
    # event_data에 datetime 객체가 있을 수 있으므로 JSON 직렬화 가능한 형태로 변환
    serialized_event_data = serialize_datetime(event_data) if event_data else {}
    
    log_payload = {
        "user_id": user_id,
        "event_type": event_type,
        "event_data": serialized_event_data
    }
    
    # 재시도 설정
    max_retries = 2  # 최대 시도 횟수
    timeout = 10  # 10초 타임아웃
    
    for attempt in range(max_retries):
        try:
            logger.info(f"로그 전송 시도 {attempt + 1}/{max_retries}: user_id={user_id}, event_type={event_type}")
            res = requests.post(api_url, json=log_payload, timeout=timeout)
            res.raise_for_status()
            logger.info(f"사용자 로그 전송 성공: user_id={user_id}, event_type={event_type}")
            return res.json()
        except requests.exceptions.Timeout:
            logger.warning(f"로그 전송 타임아웃 (시도 {attempt + 1}/{max_retries}): user_id={user_id}, event_type={event_type}")
            if attempt == max_retries - 1:
                logger.error(f"로그 전송 최종 실패 (타임아웃): user_id={user_id}, event_type={event_type}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"로그 서비스 연결 실패 (시도 {attempt + 1}/{max_retries}): user_id={user_id}, event_type={event_type}")
            if attempt == max_retries - 1:
                logger.error(f"로그 전송 최종 실패 (연결 오류): user_id={user_id}, event_type={event_type}")
        except Exception as e:
            logger.error(f"로그 전송 중 예상치 못한 오류: user_id={user_id}, event_type={event_type}, 오류={e}")
            break
    
    return None
