# SQLAlchemy 로깅 제어 가이드

## 개요
이 가이드는 SQLAlchemy 로깅을 제어하고 규격화하는 방법을 설명합니다.

## 기능
- ✅ SQLAlchemy 로깅 완전 비활성화
- ✅ SQLAlchemy 로깅 레벨 조정
- ✅ SQL 쿼리 표시/숨김 제어
- ✅ 환경별 로깅 설정
- ✅ 환경 변수를 통한 제어

## 사용 방법

### 1. 기본 사용법

```python
from common.logger import get_logger

# SQLAlchemy 로깅 비활성화 (기본값)
logger = get_logger("my_app")

# SQLAlchemy 로깅 활성화
logger = get_logger(
    "my_app",
    sqlalchemy_logging={
        'enable': True,
        'level': 'INFO',
        'show_sql': True,
        'show_parameters': False,
        'show_echo': False
    }
)
```

### 2. 환경별 설정 사용

```python
from common.logging_config import get_environment_logging_config, get_logger

# 환경별 설정 가져오기
config = get_environment_logging_config('development')
logger = get_logger("my_app", **config)

# 또는 직접 환경 지정
logger = get_logger(
    "my_app",
    level="DEBUG",
    sqlalchemy_logging=get_sqlalchemy_logging_config('development')
)
```

### 3. 환경 변수 사용

```bash
# SQLAlchemy 로깅 활성화
export SQLALCHEMY_LOGGING=true
export SQLALCHEMY_LOG_LEVEL=INFO
export SQLALCHEMY_SHOW_SQL=true

# SQLAlchemy 로깅 비활성화
export SQLALCHEMY_LOGGING=false
export SQLALCHEMY_LOG_LEVEL=ERROR
```

### 4. 빠른 설정 함수 사용

```python
from common.logger import setup_development_logging, setup_production_logging

# 개발 환경용 로거 (SQL 쿼리 표시)
dev_logger = setup_development_logging()

# 프로덕션 환경용 로거 (SQLAlchemy 로깅 비활성화)
prod_logger = setup_production_logging()
```

### 5. 수동으로 SQLAlchemy 로깅 제어

```python
from common.logging_config import disable_sqlalchemy_logging, set_sqlalchemy_log_level

# SQLAlchemy 로깅 완전 비활성화
disable_sqlalchemy_logging()

# SQLAlchemy 로깅 레벨만 조정
set_sqlalchemy_log_level('WARNING')
```

## 환경별 권장 설정

### Development (개발)
```python
{
    'enable': True,
    'level': 'INFO',
    'show_sql': True,
    'show_parameters': False,
    'show_echo': False
}
```

### Testing (테스트)
```python
{
    'enable': True,
    'level': 'WARNING',
    'show_sql': False,
    'show_parameters': False,
    'show_echo': False
}
```

### Staging (스테이징)
```python
{
    'enable': False,
    'level': 'WARNING',
    'show_sql': False,
    'show_parameters': False,
    'show_echo': False
}
```

### Production (프로덕션)
```python
{
    'enable': False,
    'level': 'ERROR',
    'show_sql': False,
    'show_parameters': False,
    'show_echo': False
}
```

## 환경 변수 목록

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `ENVIRONMENT` | `development` | 환경 설정 (development, testing, staging, production) |
| `SQLALCHEMY_LOGGING` | `false` | SQLAlchemy 로깅 활성화 여부 |
| `SQLALCHEMY_LOG_LEVEL` | `WARNING` | SQLAlchemy 로깅 레벨 |
| `SQLALCHEMY_SHOW_SQL` | `false` | SQL 쿼리 표시 여부 |
| `SQLALCHEMY_SHOW_PARAMETERS` | `false` | SQL 파라미터 표시 여부 |
| `SQLALCHEMY_ECHO` | `false` | SQLAlchemy echo 모드 여부 |

## 주의사항

1. **성능**: SQLAlchemy 로깅을 활성화하면 성능에 영향을 줄 수 있습니다.
2. **보안**: 프로덕션 환경에서는 민감한 정보가 로그에 노출되지 않도록 주의하세요.
3. **로그 레벨**: `DEBUG` 레벨은 매우 상세한 정보를 출력하므로 개발 환경에서만 사용하세요.

## 문제 해결

### SQLAlchemy 로깅이 여전히 보이는 경우
```python
# 모든 SQLAlchemy 로거를 강제로 비활성화
from common.logging_config import disable_sqlalchemy_logging
disable_sqlalchemy_logging()
```

### 특정 SQLAlchemy 로거만 제어하고 싶은 경우
```python
import logging

# 특정 로거만 설정
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
```

### 데이터베이스 연결 시 echo 파라미터 제어
```python
# SQLAlchemy 엔진 생성 시
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://user:pass@localhost/dbname',
    echo=False  # SQLAlchemy echo 비활성화
)
```
