"""
BackgroundTasks용 로그 API 호출 함수 (.env config 사용)
"""
import requests
from common.config import get_settings
from common.logger import get_logger

settings = get_settings()
logger = get_logger("log_utils")
api_url = settings.log_api_url   # .env에서 불러옴

def check_log_service_health():
    """
    로그 서비스 상태 확인
    """
    try:
        # 헬스체크 엔드포인트가 있다면 사용
        health_url = api_url.replace('/log/', '/log/health')
        response = requests.get(health_url, timeout=5)
        return response.status_code == 200
    except:
        # 헬스체크가 없다면 기본 엔드포인트로 확인
        try:
            response = requests.get(api_url, timeout=5)
            return response.status_code in [200, 405]  # 405는 Method Not Allowed (POST만 허용)
        except:
            return False

def send_user_log(user_id: int, event_type: str, event_data: dict = None):
    """
    사용자 행동 로그를 로그 서비스로 전송 (BackgroundTasks)
    """
    # 로그 서비스 상태 확인
    if not check_log_service_health():
        logger.warning(f"로그 서비스가 응답하지 않음: user_id={user_id}, event_type={event_type}")
        return None
    
    log_payload = {
        "user_id": user_id,
        "event_type": event_type,
        "event_data": event_data or {}
    }
    
    # 재시도 설정
    max_retries = 3
    timeout = 10  # 2초에서 10초로 증가
    
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
