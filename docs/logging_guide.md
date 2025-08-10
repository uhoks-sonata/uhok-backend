# 로깅 시스템 사용 가이드

## 개요

이 프로젝트는 `common/logger.py`를 기반으로 한 통합 로깅 시스템을 제공합니다. 모든 서비스와 모듈에서 일관된 방식으로 로깅을 수행할 수 있습니다.

## 주요 기능

- ✅ **터미널 출력**: 기본적으로 활성화 (컬러 지원)
- ❌ **파일 저장**: 현재 비활성화됨
- ✅ **구조화된 로깅**: JSON 형식 지원
- ✅ **로그 레벨별 색상 구분**: 가독성 향상
- ❌ **자동 로그 로테이션**: 파일 로깅과 함께 비활성화됨

## 기본 사용법

### 1. 로거 생성

```python
from common.logger import get_logger

# 기본 로거
logger = get_logger("my_service")

# 고급 설정 로거
logger = get_logger(
    name="my_service",
    level="DEBUG",
    enable_file_logging=True,
    enable_json_format=False
)
```

### 2. 로그 레벨별 사용

```python
logger.debug("디버그 정보")
logger.info("일반 정보")
logger.warning("경고 메시지")
logger.error("오류 메시지")
logger.critical("치명적 오류")
```

### 3. 컨텍스트 정보와 함께 로깅

```python
from common.logger import log_with_context

log_with_context(
    logger, 
    "INFO", 
    "사용자 로그인", 
    user_id=123, 
    ip_address="192.168.1.1"
)
```

## 환경 변수 설정

`.env` 파일에 다음 설정을 추가하여 로깅을 제어할 수 있습니다:

```bash
# 로그 레벨 설정
LOG_LEVEL=INFO

# 파일 로깅 활성화 (현재 비활성화됨)
# ENABLE_FILE_LOGGING=true

# JSON 형식 로깅
LOG_JSON_FORMAT=false
```

## 로그 포맷

### 기본 포맷
```
[2024-01-01 12:00:00] INFO - my_service - 메시지 내용
```

### JSON 포맷
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "level": "INFO",
  "logger": "my_service",
  "message": "메시지 내용",
  "module": "my_module",
  "function": "my_function",
  "line": 42
}
```

## 파일 로깅

**⚠️ 현재 파일 로깅 기능이 비활성화되어 있습니다.**

파일 로깅이 활성화되면 `logs/` 디렉토리에 로그 파일이 생성됩니다:

- `my_service.log`: 현재 로그 파일
- `my_service.log.1`: 첫 번째 백업 파일
- `my_service.log.2`: 두 번째 백업 파일
- ...

## 모범 사례

### 1. 서비스별 로거 이름 사용

```python
# 좋은 예
logger = get_logger("user_service")
logger = get_logger("order_service")

# 피해야 할 예
logger = get_logger("logger")
logger = get_logger("log")
```

### 2. 적절한 로그 레벨 사용

```python
# DEBUG: 개발 중 상세 정보
logger.debug(f"Processing user data: {user_data}")

# INFO: 일반적인 작업 진행 상황
logger.info(f"User {user_id} logged in successfully")

# WARNING: 잠재적 문제
logger.warning(f"Rate limit approaching for user {user_id}")

# ERROR: 오류 상황
logger.error(f"Database connection failed: {str(e)}")

# CRITICAL: 시스템 중단 가능성
logger.critical("Database cluster is down")
```

### 3. 예외 처리와 함께 사용

```python
try:
    result = process_data(data)
    logger.info(f"Data processed successfully: {result}")
except Exception as e:
    logger.error(f"Data processing failed: {str(e)}", exc_info=True)
    raise
```

### 4. 성능 고려사항

```python
# 좋은 예: 조건부 로깅
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Expensive operation result: {expensive_operation()}")

# 피해야 할 예: 항상 실행되는 연산
logger.debug(f"Expensive operation result: {expensive_operation()}")
```

## 로깅 설정 예시

### 개발 환경
```python
logger = get_logger(
    name="dev_service",
    level="DEBUG",
    enable_file_logging=False,
    enable_json_format=False
)
```

### 프로덕션 환경
```python
logger = get_logger(
    name="prod_service",
    level="INFO",
    enable_file_logging=False,  # 현재 비활성화됨
    enable_json_format=True
)
```

### 테스트 환경
```python
logger = get_logger(
    name="test_service",
    level="WARNING",
    enable_file_logging=False,
    enable_json_format=False
)
```

## 문제 해결

### 로그가 출력되지 않는 경우
1. 로그 레벨 확인
2. 핸들러 설정 확인
3. 로거 이름 중복 확인

### 파일 로깅이 작동하지 않는 경우
1. **현재 파일 로깅 기능이 비활성화되어 있습니다**
2. `logs/` 디렉토리 권한 확인
3. 디스크 공간 확인
4. 파일 경로 설정 확인

### 성능 문제가 있는 경우
1. 로그 레벨을 INFO 이상으로 설정
2. 파일 로깅 비활성화
3. JSON 포맷 비활성화

## 추가 정보

더 자세한 정보는 `common/logger.py` 파일의 주석을 참조하세요.
