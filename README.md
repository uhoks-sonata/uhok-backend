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
- **웹 프레임워크**: FastAPI 0.116.1 (비동기 처리, 자동 API 문서 생성)
- **데이터베이스**: 
  - MariaDB (인증/서비스 데이터) - asyncmy 드라이버
  - PostgreSQL (로그/추천 데이터) - asyncpg 드라이버, pgvector 확장
- **캐시**: Redis 5.2.1 (상품 데이터, 세션 관리)
- **ML 서비스**: 별도 컨테이너 (uhok-ml-inference) - SentenceTransformer 모델
- **컨테이너**: Docker, Docker Compose (마이크로서비스 아키텍처)
- **인증**: JWT (HS256), OAuth2PasswordBearer
- **로깅**: 구조화된 JSON 로깅, BackgroundTasks

### 마이크로서비스 아키텍처
```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                    │
│  - CORS 설정, 라우터 통합, 공통 미들웨어                    │
│  - JWT 인증, 요청/응답 로깅, 헬스체크                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───▼───┐    ┌───────▼───────┐    ┌────▼────┐
│ User  │    │   Order       │    │ Recipe  │
│ Service│    │   Service     │    │ Service │
│       │    │               │    │         │
│ - JWT │    │ - 통합 주문   │    │ - ML    │
│ - 인증│    │ - 결제 처리   │    │ - 벡터  │
│ - 회원│    │ - 상태 관리   │    │ - 추천  │
└───────┘    └───────────────┘    └─────────┘
    │                 │                 │
    │    ┌────────────▼────────────┐    │
    │    │    HomeShopping         │    │
    │    │    Service              │    │
    │    │                         │    │
    │    │ - 편성표 관리           │    │
    │    │ - 상품 검색             │    │
    │    │ - 라이브 스트리밍       │    │
    │    │ - 찜 기능               │    │
    │    └─────────────────────────┘    │
    │                 │                 │
    │    ┌────────────▼────────────┐    │
    │    │       KOK Service       │    │
    │    │                         │    │
    │    │ - 상품 관리             │    │
    │    │ - 장바구니              │    │
    │    │ - 리뷰 시스템           │    │
    │    │ - 캐싱 최적화           │    │
    │    └─────────────────────────┘    │
    │                 │                 │
    │    ┌────────────▼────────────┐    │
    │    │      Log Service        │    │
    │    │                         │    │
    │    │ - 사용자 행동 로그      │    │
    │    │ - 이벤트 추적           │    │
    │    │ - 분석 지원             │    │
    │    └─────────────────────────┘    │
    │                                   │
    └───────────────────────────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───▼───┐    ┌───────▼───────┐    ┌────▼────┐
│MariaDB│    │  PostgreSQL   │    │  Redis   │
│       │    │  + pgvector   │    │          │
│ - 인증│    │               │    │ - 캐시   │
│ - 서비스│  │ - 로그 데이터 │    │ - 세션   │
│ - 주문│    │ - 벡터 임베딩 │    │ - 상품   │
└───────┘    └───────────────┘    └─────────┘
```

### 서비스 구조
```
uhok-backend/
├── gateway/                 # API Gateway (진입점)
│   └── main.py             # FastAPI 앱, 라우터 통합, CORS 설정
├── common/                  # 공통 모듈
│   ├── auth/               # JWT 인증 및 보안
│   │   └── jwt_handler.py  # 토큰 생성/검증, 블랙리스트 관리
│   ├── database/           # DB 연결 관리
│   │   ├── base_mariadb.py # MariaDB 기본 설정
│   │   ├── base_postgres.py# PostgreSQL 기본 설정
│   │   ├── mariadb_auth.py # 인증 DB 연결
│   │   ├── mariadb_service.py # 서비스 DB 연결
│   │   ├── postgres_log.py # 로그 DB 연결
│   │   └── postgres_recommend.py # 추천 DB 연결
│   ├── dependencies.py     # FastAPI 의존성 주입
│   ├── config.py          # 환경 변수 및 설정 관리
│   ├── log_utils.py       # 로깅 유틸리티
│   └── keyword_extraction.py # 키워드 추출 로직
├── services/               # 비즈니스 서비스
│   ├── user/              # 사용자 관리
│   │   ├── models/        # SQLAlchemy 모델
│   │   ├── schemas/       # Pydantic 스키마
│   │   ├── crud/          # 데이터베이스 CRUD
│   │   └── routers/       # FastAPI 라우터
│   ├── order/             # 주문 관리 (통합)
│   │   ├── models/        # 주문, 결제 모델
│   │   ├── schemas/       # 주문, 결제 스키마
│   │   ├── crud/          # 주문 CRUD, 결제 로직
│   │   └── routers/       # 주문, 결제, 웹훅 라우터
│   ├── recipe/            # 레시피 추천
│   │   ├── models/        # 레시피 모델
│   │   ├── schemas/       # 추천 스키마
│   │   ├── crud/          # 추천 CRUD
│   │   ├── utils/         # ML 연동, 벡터 검색
│   │   └── routers/       # 추천 라우터
│   ├── homeshopping/      # 홈쇼핑
│   │   ├── models/        # 홈쇼핑 모델
│   │   ├── schemas/       # 홈쇼핑 스키마
│   │   ├── crud/          # 홈쇼핑 CRUD
│   │   ├── utils/         # 키워드 추출, 추천
│   │   ├── static/        # 정적 파일 (JS, CSS)
│   │   ├── templates/     # HTML 템플릿
│   │   └── routers/       # 홈쇼핑 라우터
│   ├── kok/               # 콕 쇼핑몰
│   │   ├── models/        # 콕 모델
│   │   ├── schemas/       # 콕 스키마
│   │   ├── crud/          # 콕 CRUD
│   │   ├── utils/         # 캐시 관리, 추천
│   │   └── routers/       # 콕 라우터
│   └── log/               # 로깅
│       ├── models/        # 로그 모델
│       ├── schemas/       # 로그 스키마
│       ├── crud/          # 로그 CRUD
│       └── routers/       # 로그 라우터
└── docs/                  # 문서
    ├── backend_structure_v_0.4.md
    ├── logging_guide.md
    └── query_optimization_summary.md
```

### 데이터 흐름
1. **API Gateway** → 요청 라우팅, 인증, 로깅
2. **서비스별 라우터** → HTTP 처리, 파라미터 검증
3. **CRUD 계층** → 비즈니스 로직, 데이터베이스 처리
4. **데이터베이스** → MariaDB (서비스), PostgreSQL (로그/추천)
5. **캐시** → Redis (성능 최적화)
6. **ML 서비스** → 별도 컨테이너 (벡터 임베딩)

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
# 로컬 DB tailscale IP
# ----------- Mariadb (비동기 드라이버: asyncmy) -----------
# MariaDB 인증 DB (운영 코드용, 비동기)
MARIADB_AUTH_URL="mysql+asyncmy://user:password@localhost:3306/AUTH_DB"
# MariaDB 인증 DB (migration용, 동기)
MARIADB_AUTH_MIGRATE_URL="mysql+pymysql://user:password@localhost:3306/AUTH_DB"
# 서비스용 DB (service_db)
MARIADB_SERVICE_URL="mysql+asyncmy://user:password@localhost:3306/SERVICE_DB"
# ----------- PostgreSQL (비동기 드라이버: asyncpg) -----------
# 추천 DB (rec_db)
POSTGRES_RECOMMEND_URL="postgresql+psycopg_async://user:password@localhost:5432/REC_DB"
# PostgreSQL 로그 DB (운영 코드용, 비동기)
POSTGRES_LOG_URL="postgresql+psycopg_async://user:password@localhost/LOG_DB"
# PostgreSQL 로그 DB (migration용, 동기)
POSTGRES_LOG_MIGRATE_URL="postgresql+psycopg2://user:password@localhost:5432/LOG_DB"

# Redis 설정
REDIS_URL=redis://localhost:6379/0

# ML 서비스 설정
ML_MODE=remote_embed
ML_SERVICE_URL=http://ml-inference:8001

# 결제 서비스 설정
PAYMENT_SERVER_URL2=http://payment-server:9002
# 웹훅 받을 주소 설정(백엔드를 본인이 열 경우 본인 IP 사용)
WEBHOOK_BASE_URL=http://<ec2-IP>:80  # ec2 인스턴스 ip

# 내부 서버 간 인증
PAYMENT_WEBHOOK_SECRET=your_webhook_secret_key
SERVICE_AUTH_TOKEN=your_auth_token
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

#### 🔐 사용자 관리 (User Service)
- `POST /api/user/signup` - 회원가입
- `POST /api/user/login` - 로그인 (OAuth2PasswordRequestForm)
- `POST /api/user/logout` - 로그아웃
- `GET /api/user/check-email` - 이메일 중복 확인
- `GET /api/user/info` - 사용자 정보 조회 (JWT 인증 필요)

#### 🛒 주문 관리 (Order Service)
**통합 주문 조회**
- `GET /api/orders` - 주문 목록 조회 (페이징 지원)
- `GET /api/orders/{order_id}` - 주문 상세 조회
- `GET /api/orders/{order_id}/delivery` - 배송 정보 조회

**콕 주문**
- `POST /api/orders/kok/carts/order` - 장바구니에서 주문 생성
- `GET /api/orders/kok/{kok_order_id}` - 콕 주문 상세 조회
- `PATCH /api/orders/kok/{kok_order_id}/status` - 콕 주문 상태 업데이트
- `GET /api/orders/kok/{kok_order_id}/status-history` - 주문 상태 이력 조회
- `POST /api/orders/kok/{kok_order_id}/auto-update` - 자동 상태 업데이트 시작
- `GET /api/orders/kok/notifications` - 콕 주문 알림 조회

**홈쇼핑 주문**
- `POST /api/orders/homeshopping/order` - 홈쇼핑 주문 생성
- `GET /api/orders/homeshopping/{hs_order_id}` - 홈쇼핑 주문 상세 조회
- `GET /api/orders/homeshopping/{hs_order_id}/status-history` - 주문 상태 이력 조회
- `POST /api/orders/homeshopping/{hs_order_id}/auto-update` - 자동 상태 업데이트 시작

#### 💳 결제 관리 (Payment Service)
- `POST /api/orders/payment/{order_id}/confirm/v1` - V1 결제 확인 (폴링 방식)
- `POST /api/orders/payment/{order_id}/confirm/v2` - V2 결제 확인 (웹훅 방식)
- `POST /api/orders/payment/webhook/v2/{tx_id}` - 결제 웹훅 수신

#### 🍳 레시피 추천 (Recipe Service)
- `GET /api/recipe/by-ingredients` - 식재료 기반 레시피 추천 (페이지별 조합)
- `GET /api/recipe/search` - 레시피명/식재료 키워드 검색
- `GET /api/recipe/{recipe_id}/rating` - 레시피 별점 조회
- `POST /api/recipe/{recipe_id}/rating` - 레시피 별점 등록
- `GET /api/recipe/{recipe_id}/status` - 레시피 식재료 상태 조회
- `GET /api/recipe/cache/stats` - 레시피 캐시 통계 조회

#### 🏪 홈쇼핑 (HomeShopping Service)
**편성표 및 상품**
- `GET /api/homeshopping/schedule` - 방송 편성표 조회 (날짜별 필터링)
- `GET /api/homeshopping/search` - 상품 검색 (키워드 기반)
- `GET /api/homeshopping/product/{live_id}` - 상품 상세 정보
- `GET /api/homeshopping/live/{live_id}` - 라이브 스트리밍 URL

**검색 이력 관리**
- `POST /api/homeshopping/search/history` - 검색 이력 저장
- `GET /api/homeshopping/search/history` - 검색 이력 조회
- `DELETE /api/homeshopping/search/history` - 검색 이력 삭제

**찜 기능**
- `POST /api/homeshopping/likes/toggle` - 상품 찜하기/해제
- `GET /api/homeshopping/likes` - 찜한 상품 목록

**추천 기능**
- `GET /api/homeshopping/product/{product_id}/kok-recommend` - 콕 유사 상품 추천
- `GET /api/homeshopping/product/{product_id}/recipe-recommend` - 레시피 추천

**알림 관리**
- `GET /api/homeshopping/notifications/orders` - 주문 알림 조회
- `GET /api/homeshopping/notifications/broadcasts` - 방송 알림 조회
- `POST /api/homeshopping/notifications/{notification_id}/read` - 알림 읽음 처리

#### 🛍️ 콕 (KOK Service)
**상품 정보**
- `GET /api/kok/discounted` - 할인 상품 목록 (캐싱 적용)
- `GET /api/kok/top-selling` - 인기 상품 목록
- `GET /api/kok/store-best` - 스토어 베스트 상품
- `GET /api/kok/product/{product_id}` - 상품 상세 정보
- `GET /api/kok/product/{product_id}/tabs` - 상품 탭 정보 (이미지)
- `GET /api/kok/product/{product_id}/reviews` - 상품 리뷰 조회
- `GET /api/kok/product/{product_id}/seller-details` - 판매자 상세 정보

**장바구니 관리**
- `POST /api/kok/cart` - 장바구니 추가
- `GET /api/kok/cart` - 장바구니 조회
- `PUT /api/kok/cart/{cart_id}` - 장바구니 수량 변경
- `DELETE /api/kok/cart/{cart_id}` - 장바구니 삭제
- `GET /api/kok/carts/recipe-recommend` - 장바구니 상품 기반 레시피 추천

**찜 기능**
- `POST /api/kok/likes/toggle` - 상품 찜하기/해제
- `GET /api/kok/likes` - 찜한 상품 목록

**검색 기능**
- `GET /api/kok/search` - 상품 검색
- `POST /api/kok/search/history` - 검색 이력 저장
- `GET /api/kok/search/history` - 검색 이력 조회
- `DELETE /api/kok/search/history` - 검색 이력 삭제

**추천 기능**
- `GET /api/kok/recommend/homeshopping/{homeshopping_product_id}` - 홈쇼핑 상품 기반 콕 추천

**알림 관리**
- `GET /api/kok/notifications` - 알림 목록 조회
- `POST /api/kok/notifications/{notification_id}/read` - 알림 읽음 처리

#### 📊 로깅 (Log Service)
**사용자 이벤트 로그**
- `POST /api/log/user/event` - 사용자 이벤트 로그 기록
- `GET /api/log/user/event/{user_id}` - 사용자별 이벤트 로그 조회
- `GET /api/log/user/event/health` - 로그 서비스 헬스체크

**사용자 활동 로그**
- `POST /api/log/user/activity` - 사용자 활동 로그 기록 (인증 필요)

#### 🔧 시스템 관리
- `GET /api/health` - API Gateway 헬스체크
- `GET /healthz` - 컨테이너 헬스체크 (Docker)

### API 문서 확인
서비스 실행 후 다음 URL에서 상세한 API 문서를 확인할 수 있습니다:
- **Swagger UI**: http://localhost:9000/docs

## 🔧 개발 가이드

### 프로젝트 구조 이해

#### 1. Gateway (API Gateway)
- **역할**: 모든 API 요청의 진입점, 라우팅 및 공통 처리
- **기능**: 
  - CORS 설정 및 미들웨어 관리
  - 라우터 통합 및 요청 라우팅
  - JWT 인증 및 권한 검증
  - 요청/응답 로깅 및 모니터링
  - 헬스체크 엔드포인트 제공
- **파일**: `gateway/main.py`

#### 2. Common 모듈
- **config.py**: 환경 변수 및 설정 관리 (Pydantic Settings)
- **database/**: 
  - 비동기 데이터베이스 연결 관리
  - MariaDB, PostgreSQL 연결 풀 설정
  - 트랜잭션 관리 및 세션 관리
- **auth/**: 
  - JWT 토큰 생성/검증
  - 토큰 블랙리스트 관리
  - OAuth2 인증 플로우
- **dependencies.py**: FastAPI 의존성 주입 (DB, 인증, 로깅)
- **log_utils.py**: 구조화된 로깅 유틸리티
- **keyword_extraction.py**: 키워드 추출 및 전처리

#### 3. Services (비즈니스 로직)
각 서비스는 계층화된 아키텍처를 따릅니다:
```
services/{service_name}/
├── models/          # SQLAlchemy 모델 (데이터베이스 스키마)
├── schemas/         # Pydantic 스키마 (API 요청/응답)
├── crud/           # 데이터베이스 CRUD (비즈니스 로직)
├── routers/        # FastAPI 라우터 (HTTP 처리)
└── utils/          # 유틸리티 함수 (헬퍼, 캐시, 추천 등)
```

### 개발 패턴

#### 1. 계층별 역할 분리
- **Router**: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
- **CRUD**: 비즈니스 로직, 데이터베이스 처리, 트랜잭션 관리
- **Model**: 데이터베이스 스키마 정의
- **Schema**: API 입출력 데이터 검증 및 직렬화

#### 2. 비동기 처리 패턴
```python
# 모든 데이터베이스 작업은 비동기로 처리
async def get_user_orders(db: AsyncSession, user_id: int):
    result = await db.execute(select(Order).where(Order.user_id == user_id))
    return result.scalars().all()

# BackgroundTasks를 사용한 비동기 로깅
async def create_order(background_tasks: BackgroundTasks):
    # 주문 생성 로직
    background_tasks.add_task(send_user_log, user_id, "order_create", data)
```

#### 3. 에러 처리 패턴
```python
# 커스텀 예외 사용
from common.errors import NotFoundException, ConflictException

async def get_product(product_id: int):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundException("상품을 찾을 수 없습니다.")
    return product
```

### 새로운 서비스 추가

1. **서비스 디렉토리 생성**
```bash
mkdir -p services/new_service/{models,schemas,crud,routers,utils}
touch services/new_service/__init__.py
```

2. **기본 파일 생성**
- `models/new_service_model.py`: SQLAlchemy 모델
- `schemas/new_service_schema.py`: Pydantic 스키마
- `crud/new_service_crud.py`: 데이터베이스 CRUD 함수
- `routers/new_service_router.py`: FastAPI 라우터
- `utils/new_service_utils.py`: 유틸리티 함수

3. **Gateway에 라우터 등록**
```python
# gateway/main.py
from services.new_service.routers.new_service_router import router as new_service_router
app.include_router(new_service_router)
```

4. **데이터베이스 마이그레이션**
```bash
# Alembic 마이그레이션 파일 생성
alembic revision --autogenerate -m "Add new service tables"
alembic upgrade head
```

### 코딩 컨벤션

#### 1. 타입 힌트
```python
# 모든 함수에 타입 힌트 추가
async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    return await db.get(User, user_id)
```

#### 2. Docstring
```python
async def create_order(
    db: AsyncSession, 
    order_data: OrderCreate, 
    user_id: int
) -> Order:
    """
    새로운 주문을 생성합니다.
    
    Args:
        db: 데이터베이스 세션
        order_data: 주문 생성 데이터
        user_id: 사용자 ID
        
    Returns:
        Order: 생성된 주문 객체
        
    Raises:
        ValidationError: 입력 데이터 검증 실패
        DatabaseError: 데이터베이스 오류
    """
```

#### 3. 로깅 패턴
```python
# 구조화된 로깅 사용
logger.info(f"주문 생성 시작: user_id={user_id}, order_data={order_data}")
logger.error(f"주문 생성 실패: user_id={user_id}, error={str(e)}")
```

### 테스트 가이드

#### 1. 단위 테스트
```python
# pytest를 사용한 비동기 테스트
@pytest.mark.asyncio
async def test_create_user():
    async with get_test_db() as db:
        user_data = UserCreate(email="test@example.com", password="password")
        user = await create_user(db, user_data)
        assert user.email == "test@example.com"
```

#### 2. API 테스트
```python
# FastAPI TestClient 사용
def test_get_products(client):
    response = client.get("/api/kok/discounted")
    assert response.status_code == 200
    assert "products" in response.json()
```

### 성능 최적화 가이드

#### 1. 데이터베이스 쿼리 최적화
- N+1 쿼리 문제 해결을 위한 JOIN 사용
- 인덱스 최적화 및 쿼리 실행 계획 분석
- 비동기 드라이버 사용으로 동시성 향상

#### 2. 캐싱 전략
- Redis를 활용한 자주 조회되는 데이터 캐싱
- 메모리 캐싱을 통한 계산 결과 재사용
- CDN을 활용한 정적 파일 최적화


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

### 인증 및 인가
- **JWT 토큰**: HS256 알고리즘을 사용한 안전한 토큰 생성
- **토큰 블랙리스트**: 로그아웃된 토큰을 Redis에 저장하여 차단
- **토큰 만료**: 설정 가능한 토큰 만료 시간 (기본 30분)
- **OAuth2**: OAuth2PasswordBearer를 사용한 표준 인증 플로우
- **서비스 간 인증**: 내부 서비스 간 Bearer 토큰 인증

### 데이터 보호
- **비밀번호 해싱**: bcrypt를 사용한 안전한 비밀번호 해싱
- **SQL 인젝션 방지**: SQLAlchemy ORM과 파라미터화된 쿼리 사용
- **XSS 방지**: 입력 데이터 검증 및 이스케이핑
- **CSRF 보호**: CORS 설정을 통한 크로스 사이트 요청 방지

### 네트워크 보안
- **CORS 설정**: 허용된 도메인만 API 접근 가능
- **HTTPS 강제**: 프로덕션 환경에서 HTTPS 사용
- **웹훅 서명 검증**: HMAC-SHA256을 사용한 웹훅 서명 검증
- **IP 화이트리스트**: 관리자 API 접근 제한

### 로깅 및 모니터링
- **보안 이벤트 로깅**: 인증 실패, 권한 위반 등 보안 이벤트 추적
- **사용자 행동 추적**: 의심스러운 활동 패턴 감지
- **API 접근 로깅**: 모든 API 요청에 대한 상세 로깅
- **에러 정보 보호**: 프로덕션에서 민감한 에러 정보 숨김

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
- **인덱스 최적화**: 자주 사용되는 쿼리에 대한 복합 인덱스 생성
- **쿼리 최적화**: N+1 쿼리 문제 해결, JOIN 최적화
- **연결 풀링**: 비동기 드라이버 (asyncmy, asyncpg) 사용
- **벡터 검색**: PostgreSQL pgvector를 활용한 고성능 벡터 유사도 검색
- **쿼리 캐싱**: 복잡한 추천 쿼리 결과 캐싱

### 캐싱 전략
- **Redis 캐싱**: 
  - 상품 데이터 (5분 TTL)
  - 사용자 세션 정보
  - 검색 결과 캐싱
  - 레시피 추천 결과 캐싱
- **메모리 캐싱**: 
  - 조합 추천 결과 캐싱
  - ML 임베딩 벡터 캐싱
- **CDN 활용**: 정적 파일 (이미지, JS, CSS) CDN 배포

### API 최적화
- **비동기 처리**: FastAPI의 async/await 패턴 활용
- **백그라운드 작업**: BackgroundTasks를 사용한 비동기 로깅
- **응답 압축**: gzip 미들웨어로 응답 크기 최적화
- **페이징**: 대용량 데이터 조회 시 페이징 적용
- **병렬 처리**: 여러 데이터베이스 쿼리 병렬 실행

### ML 서비스 최적화
- **벡터 인덱싱**: pgvector의 HNSW 인덱스 활용
- **배치 처리**: 여러 쿼리를 배치로 처리하여 네트워크 오버헤드 감소
- **모델 캐싱**: ML 모델 로딩 최적화
- **임베딩 캐싱**: 자주 사용되는 임베딩 벡터 캐싱

### 모니터링 및 로깅
- **구조화된 로깅**: JSON 형식의 일관된 로그 구조
- **성능 메트릭**: API 응답 시간, 데이터베이스 쿼리 시간 추적
- **에러 추적**: 상세한 에러 로깅 및 스택 트레이스
- **사용자 행동 분석**: 사용자 이벤트 로깅으로 개인화 개선

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

## 문서
- **API 문서**: http://localhost:9000/docs
- **개발 가이드**: 각 서비스별 README.md
- **아키텍처 문서**: `docs/` 디렉토리

---

**UHOK Backend** - 레시피 추천을 위한 고성능 마이크로서비스 백엔드
