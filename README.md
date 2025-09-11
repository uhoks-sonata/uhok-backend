# UHOK Backend

U+콕&홈쇼핑 기반 사용자 맞춤 식재료 및 레시피 추천 서비스입니다. FastAPI 기반의 마이크로서비스 아키텍처로 구성되어 있으며, 사용자 관리, 주문 처리, 레시피 추천, 로깅 등의 핵심 기능을 제공합니다.

## 🚀 주요 기능

### 👤 사용자 관리 (User Service)
- **회원가입/로그인**: JWT 기반 인증 시스템
- **보안 기능**: JWT 블랙리스트, 토큰 검증
- **사용자 정보 관리**: 프로필 조회 및 관리

### 🏪 홈쇼핑 (HomeShopping Service)
- **상품 관리**: 홈쇼핑 상품 정보 및 이미지 관리
- **편성표 조회**: 방송 스케줄 및 채널별 편성표
- **상품 검색**: 키워드 기반 상품 검색 및 필터링
- **검색 이력**: 사용자별 검색 기록 관리
- **상품 상세**: 상품 상세 정보, 이미지, 리뷰 조회
- **찜 기능**: 상품 찜하기/해제 및 찜 목록 관리
- **라이브 스트리밍**: 실시간 방송 플레이어 및 URL 관리
- **상품 분류**: 식재료 기반 상품 분류 시스템
- **KOK 연동**: 콕 상품 기반 홈쇼핑 상품 추천

### 🛍️ 콕 (KOK Service)
- **상품 관리**: 콕 상품 정보, 가격, 이미지, 상세 정보 관리
- **할인 상품**: 특가 상품 조회 및 성능 최적화된 리스트 제공
- **상품 상세**: 상품 상세 정보, 리뷰, 가격 이력 조회
- **리뷰 시스템**: 상품 리뷰 조회 및 통계 제공
- **장바구니**: 상품 장바구니 추가/삭제/수량 변경
- **찜 기능**: 상품 찜하기/해제 및 찜 목록 관리
- **검색 기능**: 상품명 기반 검색 및 검색 이력 관리
- **캐시 최적화**: Redis 기반 캐싱으로 성능 향상
- **홈쇼핑 연동**: 홈쇼핑 상품 기반 콕 상품 추천
- **알림 관리**: 상품 관련 알림 및 통지 관리

### 🛒 주문 관리 (Order Service)
- **통합 주문 시스템**: 콕(KOK) 및 홈쇼핑 주문 통합 관리
- **결제 처리**: 외부 결제 API 연동 및 결제 확인
- **주문 조회**: 주문 내역, 배송 정보 조회
- **통계 기능**: 주문 통계 및 분석
- **폴링 방식**: V1 결제 확인 API (외부 결제 API 응답 대기)
- **주문 생성**: 콕 및 홈쇼핑 주문 생성 및 관리
- **결제 상태 관리**: 결제 진행 상태 추적 및 업데이트

### 🍳 레시피 추천 (Recipe Service)
- **하이브리드 추천**: 레시피명 기반 + 벡터 유사도 기반 추천
- **식재료 기반 추천**: 보유 재료 기반 레시피 추천
- **ML 서비스 연동**: 별도 ML 서비스와 연동하여 임베딩 생성
- **벡터 유사도**: PostgreSQL pgvector를 활용한 고성능 벡터 검색
- **다국어 지원**: paraphrase-multilingual-MiniLM-L12-v2 모델 사용
- **재료 매칭**: 식재료 기반 레시피 필터링 및 매칭 알고리즘
- **성능 최적화**: N+1 쿼리 해결, 캐싱, 비동기 처리
- **원격 ML 어댑터**: ML 서비스와의 HTTP 통신 관리

### 📊 로깅 (Log Service)
- **사용자 행동 로그**: 사용자 활동 추적 및 분석
- **이벤트 로그**: 시스템 이벤트 기록 (회원가입, 로그인, 주문, 결제 등)
- **구조화된 로깅**: JSON 형식의 일관된 로그 구조
- **이벤트 타입 관리**: 표준화된 이벤트 타입 체계
- **사용자별 로그 조회**: 특정 사용자의 로그 이력 조회
- **실시간 로그 적재**: BackgroundTasks를 통한 비동기 로그 처리
- **분석 지원**: 사용자 분석, 추천, 마케팅, 통계 활용

## 🏗️ 아키텍처

### 기술 스택
- **웹 프레임워크**: FastAPI 0.116.1
- **데이터베이스**: MariaDB (인증/서비스), PostgreSQL (로그/추천)
- **캐시**: Redis 5.2.1
- **ML 서비스**: 별도 컨테이너 (uhok-ml-inference)
- **컨테이너**: Docker, Docker Compose

### 서비스 구조
```
uhok-backend/
├── gateway/                 # API Gateway (진입점)
├── common/                  # 공통 모듈
│   ├── auth/               # JWT 인증
│   ├── database/           # DB 연결 관리
│   ├── dependencies.py     # 의존성 주입
│   └── config.py          # 설정 관리
├── services/               # 비즈니스 서비스
│   ├── user/              # 사용자 관리 (JWT 인증, 블랙리스트)
│   ├── order/             # 주문 관리 (콕/홈쇼핑 통합, 결제 처리)
│   ├── recipe/            # 레시피 추천 (ML 연동, 벡터 검색)
│   ├── homeshopping/      # 홈쇼핑 (편성표, 검색, 찜, 라이브)
│   ├── kok/               # 콕 (상품, 장바구니, 리뷰, 캐시)
│   └── log/               # 로그 (사용자 행동, 이벤트 추적)
└── docs/                  # 문서
```

## 🚀 빠른 시작

### 사전 요구사항
- Python 3.13.5 (Docker Python 3.11+)
- Docker & Docker Compose
- MariaDB
- PostgreSQL (pgvector 확장)
- Redis

### 환경 설정

1. **저장소 클론**
```bash
git clone <repository-url>
cd uhok-backend
```

2. **환경 변수 설정**
```bash
# .env 파일 생성
cp .env.example .env

# 환경 변수 설정 (예시)
APP_NAME=uhok-backend
DEBUG=true
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 데이터베이스 설정
MARIADB_AUTH_URL=mysql+pymysql://user:password@localhost:3306/auth_db
MARIADB_SERVICE_URL=mysql+pymysql://user:password@localhost:3306/service_db
POSTGRES_RECOMMEND_URL=postgresql://user:password@localhost:5432/recommend_db
POSTGRES_LOG_URL=postgresql://user:password@localhost:5432/log_db

# Redis 설정
REDIS_URL=redis://localhost:6379/0

# ML 서비스 설정
ML_SERVICE_URL=http://ml-inference:8001
```

3. **의존성 설치**
```bash
pip install -r requirements.txt
```

4. **데이터베이스 마이그레이션**
```bash
# MariaDB 마이그레이션
alembic -c alembic_mariadb_auth.ini upgrade head

# PostgreSQL 마이그레이션
alembic -c alembic_postgres_log.ini upgrade head
```

5. **서비스 실행**
```bash
# 개발 모드
uvicorn gateway.main:app --host 0.0.0.0 --port 9000 --reload

# Docker로 실행
docker build -t uhok-backend .
docker run -p 9000:9000 uhok-backend
```

## 📚 API 문서

### 주요 엔드포인트

#### 사용자 관리
- `POST /api/user/signup` - 회원가입
- `POST /api/user/login` - 로그인
- `POST /api/user/logout` - 로그아웃
- `GET /api/user/info` - 사용자 정보 조회

#### 주문 관리
- `GET /api/orders` - 주문 목록 조회
- `GET /api/orders/{order_id}` - 주문 상세 조회
- `POST /api/orders/{order_id}/payment/confirm/v1` - 결제 확인

#### 레시피 추천
- `POST /api/recommend/recipe` - 레시피명 기반 추천
- `POST /api/recommend/ingredient` - 식재료 기반 추천

#### 홈쇼핑
- `GET /api/homeshopping/schedule` - 방송 편성표 조회
- `GET /api/homeshopping/search` - 상품 검색
- `POST /api/homeshopping/search/history` - 검색 이력 저장
- `GET /api/homeshopping/search/history` - 검색 이력 조회
- `DELETE /api/homeshopping/search/history` - 검색 이력 삭제
- `GET /api/homeshopping/products/{live_id}` - 상품 상세 정보
- `POST /api/homeshopping/likes/toggle` - 상품 찜하기/해제
- `GET /api/homeshopping/likes` - 찜한 상품 목록
- `GET /api/homeshopping/live/{live_id}` - 라이브 스트리밍 URL
- `GET /api/homeshopping/notifications` - 알림 목록 조회
- `POST /api/homeshopping/notifications/{notification_id}/read` - 알림 읽음 처리
- `GET /api/homeshopping/recommend/kok/{kok_product_id}` - 콕 상품 기반 홈쇼핑 추천

#### 콕
- `GET /api/kok/discounted` - 할인 상품 목록
- `GET /api/kok/products/{product_id}` - 상품 상세 정보
- `GET /api/kok/products/{product_id}/tabs` - 상품 탭 정보
- `GET /api/kok/products/{product_id}/reviews` - 상품 리뷰 조회
- `POST /api/kok/cart` - 장바구니 추가
- `GET /api/kok/cart` - 장바구니 조회
- `PUT /api/kok/cart/{cart_id}` - 장바구니 수량 변경
- `DELETE /api/kok/cart/{cart_id}` - 장바구니 삭제
- `POST /api/kok/likes/toggle` - 상품 찜하기/해제
- `GET /api/kok/likes` - 찜한 상품 목록
- `GET /api/kok/search` - 상품 검색
- `POST /api/kok/search/history` - 검색 이력 저장
- `GET /api/kok/search/history` - 검색 이력 조회
- `GET /api/kok/notifications` - 알림 목록 조회
- `POST /api/kok/notifications/{notification_id}/read` - 알림 읽음 처리
- `GET /api/kok/recommend/homeshopping/{homeshopping_product_id}` - 홈쇼핑 상품 기반 콕 추천

#### 로깅
- `POST /log/` - 로그 적재
- `GET /log/user/{user_id}` - 사용자 로그 조회

### API 문서 확인
서비스 실행 후 다음 URL에서 상세한 API 문서를 확인할 수 있습니다:
- **Swagger UI**: http://localhost:9000/docs

## 🔧 개발 가이드

### 프로젝트 구조 이해

#### 1. Gateway (API Gateway)
- **역할**: 모든 API 요청의 진입점
- **기능**: CORS 설정, 라우터 통합, 공통 미들웨어
- **파일**: `gateway/main.py`

#### 2. Common 모듈
- **config.py**: 환경 변수 및 설정 관리
- **database/**: 데이터베이스 연결 관리
- **auth/**: JWT 인증 및 보안
- **dependencies.py**: FastAPI 의존성 주입

#### 3. Services (비즈니스 로직)
각 서비스는 다음과 같은 구조를 가집니다:
```
services/{service_name}/
├── models/          # SQLAlchemy 모델
├── schemas/         # Pydantic 스키마
├── crud/           # 데이터베이스 CRUD
├── routers/        # FastAPI 라우터
└── utils/          # 유틸리티 함수
```

### 새로운 서비스 추가

1. **서비스 디렉토리 생성**
```bash
mkdir -p services/new_service/{models,schemas,crud,routers,utils}
```

2. **기본 파일 생성**
- `models/`: SQLAlchemy 모델
- `schemas/`: Pydantic 스키마
- `crud/`: 데이터베이스 CRUD 함수
- `routers/`: FastAPI 라우터

3. **Gateway에 라우터 등록**
```python
# gateway/main.py
from services.new_service.routers.new_service_router import router as new_service_router
app.include_router(new_service_router)
```

## 🧪 테스트

### 단위 테스트 실행
```bash
# 전체 테스트
pytest

# 특정 서비스 테스트
pytest services/user/tests/

# 커버리지 포함
pytest --cov=services
```

### API 테스트
```bash
# 헬스체크
curl http://localhost:9000/api/health

# 사용자 로그인 테스트
curl -X POST "http://localhost:9000/api/user/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'
```

## 📊 모니터링 및 로깅

### 로깅 시스템
- **구조화된 로그**: JSON 형식의 구조화된 로그
- **서비스별 분리**: 각 서비스의 독립적 로그 관리
- **레벨별 관리**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### 헬스체크
- **API 헬스체크**: `/api/health` - 서비스 상태 확인
- **컨테이너 헬스체크**: `/healthz` - 컨테이너 상태 확인

### 성능 모니터링
- **응답 시간**: API 응답 시간 추적
- **에러율**: HTTP 에러 코드별 발생률
- **리소스 사용량**: CPU, 메모리 사용률

## 🚀 배포

### Docker 배포
```bash
# 이미지 빌드
docker build -t uhok-backend:latest .

# 컨테이너 실행
docker run -d \
  --name uhok-backend \
  -p 9000:9000 \
  --env-file .env \
  uhok-backend:latest
```

### Docker Compose 배포
```bash
# 전체 스택 실행
docker-compose -f ../uhok-deploy/docker-compose.web.yml up -d

# 백엔드만 실행
docker-compose -f ../uhok-deploy/docker-compose.web.yml up -d backend
```

## 🔒 보안

### JWT 인증
- **토큰 기반 인증**: JWT 액세스 토큰 사용
- **블랙리스트 관리**: 로그아웃된 토큰 차단
- **토큰 만료**: 설정 가능한 토큰 만료 시간

### 데이터 보호
- **비밀번호 해싱**: bcrypt를 사용한 안전한 비밀번호 저장
- **SQL 인젝션 방지**: SQLAlchemy ORM 사용
- **CORS 설정**: 허용된 도메인만 접근 가능

## 🐛 문제 해결

### 일반적인 문제

#### 1. 데이터베이스 연결 실패
```bash
# 연결 정보 확인
echo $MARIADB_SERVICE_URL
echo $POSTGRES_RECOMMEND_URL

# 데이터베이스 상태 확인
docker ps | grep -E "(mariadb|postgres|redis)"
```

#### 2. JWT 토큰 오류
```bash
# JWT 설정 확인
echo $JWT_SECRET
echo $JWT_ALGORITHM

# 토큰 검증
python -c "import jwt; print(jwt.decode('your-token', 'your-secret', algorithms=['HS256']))"
```

#### 3. ML 서비스 연결 실패
```bash
# ML 서비스 상태 확인
curl http://ml-inference:8001/health

# 네트워크 연결 확인
docker network ls
docker network inspect uhok_default
```

### 로그 확인
```bash
# 애플리케이션 로그
docker logs uhok-backend

# 실시간 로그
docker logs -f uhok-backend

# 특정 서비스 로그
docker logs uhok-backend 2>&1 | grep "user_router"
```

## 📈 성능 최적화

### 데이터베이스 최적화
- **인덱스 최적화**: 자주 사용되는 쿼리에 대한 인덱스 생성
- **쿼리 최적화**: N+1 쿼리 문제 해결
- **연결 풀링**: 데이터베이스 연결 풀 최적화

### 캐싱 전략
- **Redis 캐싱**: 자주 조회되는 데이터 캐싱
- **쿼리 결과 캐싱**: 복잡한 쿼리 결과 캐싱
- **세션 캐싱**: 사용자 세션 정보 캐싱

### API 최적화
- **비동기 처리**: FastAPI의 비동기 기능 활용
- **백그라운드 작업**: BackgroundTasks를 사용한 비동기 처리
- **응답 압축**: gzip 압축으로 응답 크기 최적화

## 🤝 기여하기

### 개발 워크플로우
1. **이슈 생성**: 새로운 기능이나 버그에 대한 이슈 생성
2. **브랜치 생성**: `feature/기능명` 또는 `fix/버그명` 브랜치 생성
3. **개발**: 코드 작성 및 테스트
4. **PR 생성**: Pull Request 생성 및 리뷰 요청
5. **병합**: 리뷰 승인 후 메인 브랜치에 병합

### 코딩 스타일
- **Python**: PEP 8 스타일 가이드 준수
- **타입 힌트**: 모든 함수에 타입 힌트 추가
- **문서화**: 모든 공개 함수에 docstring 추가
- **테스트**: 새로운 기능에 대한 테스트 코드 작성

## 📞 지원 및 문의

### 문제 신고
- **GitHub Issues**: 버그 신고 및 기능 요청
- **이메일**: 개발팀 이메일로 문의

### 문서
- **API 문서**: http://localhost:9000/docs
- **개발 가이드**: 각 서비스별 README.md
- **아키텍처 문서**: `docs/` 디렉토리

---

**UHOK Backend** - 레시피 추천을 위한 고성능 마이크로서비스 백엔드
