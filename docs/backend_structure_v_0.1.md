# 📄 backend/ 설계 문서 (로컬 개발 기준)

## 👩🏻‍💻 프로젝트 개요

- LG U+의 **U+콕 & 홈쇼핑 기반 사용자 맞춤 식재료 및 레시피 추천 플랫폼**
- 백엔드는 **FastAPI 기반 MSA 구조**로 구성되며,
- 각 서비스는 기능별로 나뉘고, gateway에서 통합 관리합니다.
- ✅ **현재 문서는 로컬 개발 환경을 기준**으로 작성되었습니다. (AWS 등 클라우드 고려는 하단 참조)

---

## 📁 전체 디렉토리 구조 (로컬 개발)

```
backend/
├── gateway/                            # API Gateway
│   ├── main.py                         # FastAPI 진입점 (전체 router 통합)
│   ├── routes/                         # (옵션) 프록시 경로 분리
│   └── config.py                       # CORS, 설정 모듈
│
├── services/
│   ├── user/                           # 사용자 관리 서비스
│   │   ├── main.py                     # (단독 실행용)
│   │   ├── routers/user_router.py
│   │   ├── models/user_model.py
│   │   ├── schemas/user_schema.py
│   │   ├── crud/user_crud.py
│   │   └── database.py
│
│   ├── kok/                            # U+콕 상품 조회/검색
│   │   ├── main.py
│   │   ├── routers/kok_router.py
│   │   ├── models/product_model.py
│   │   ├── schemas/product_schema.py
│   │   ├── crud/kok_crud.py
│   │   └── database.py
│
│   ├── home_shopping/                 # 홈쇼핑 방송, 편성표
│   │   ├── main.py
│   │   ├── routers/home_router.py
│   │   ├── models/show_model.py
│   │   ├── schemas/show_schema.py
│   │   ├── crud/show_crud.py
│   │   └── database.py
│
│   ├── recipe/                        # 레시피 추천
│   │   ├── main.py
│   │   ├── routers/recipe_router.py
│   │   ├── models/recipe_model.py
│   │   ├── schemas/recipe_schema.py
│   │   ├── crud/recipe_crud.py
│   │   └── database.py
│
│   ├── recommend/                     # 추천 알고리즘 (word2vec, BERT, faiss)
│   │   ├── main.py
│   │   ├── routers/recommend_router.py
│   │   ├── rankers/bert_ranker.py
│   │   ├── rankers/word2vec_ranker.py
│   │   ├── vector_store/faiss_loader.py
│   │   ├── crud/recommend_crud.py
│   │   └── database.py
│
│   └── log/                           # 사용자 행동 로그 수집
│       ├── main.py
│       ├── routers/log_router.py
│       ├── models/log_model.py
│       ├── schemas/log_schema.py
│       └── crud/log_crud.py
│
├── common/                            # 공통 유틸, 인증, 예외처리
│   ├── auth/jwt_handler.py
│   ├── config.py
│   ├── dependencies.py
│   ├── errors.py
│   ├── logger.py
│   └── utils.py
│
├── docker/                            # Docker 로컬 실행 환경
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── nginx/nginx.conf
│
├── tests/                             # 서비스별 테스트
│   ├── user/test_user.py
│   └── ...
│
├── .env                               # 환경 변수 설정
├── requirements.txt                   # 의존 패키지 목록
├── README.md
└── .github/workflows/ci.yml           # GitHub Actions CI/CD (선택)
```

## 🔗 서비스 간 연결 관계

```
[ gateway/main.py ]
 └── include_router(user_router)
 └── include_router(kok_router)
 └── include_router(home_router)
 └── include_router(recipe_router)
 └── include_router(recommend_router)
 └── include_router(log_router)

[ services/ */main.py ]
 └── FastAPI 앱 실행 (테스트용 단독)
 └── router include + DB 초기화 + CORS 설정

[ 각 서비스 ]
 ├── routers/ → API URL 정의
 ├── services/ → 비즈니스 로직 처리
 ├── models/ → SQLAlchemy ORM
 ├── schemas/ → 요청/응답 스키마 정의
 └── database.py → Session 관리, engine 생성

[ common/ ]
 ├── JWT 발행 및 인증
 ├── 공통 예외 핸들러
 └── 로깅 설정
```

---

## 🚀 실행 방법

### ✅ 전체 Gateway 기반 실행

```bash
uvicorn gateway.main:app --reload --port 8000
```

### ✅ 개별 서비스 단독 실행 (예: user)

```bash
uvicorn services.user.main:app --reload --port 8001
```

---

## 🔬 테스트 구조

```
tests/
├── user/
│   └── test_user.py
├── recipe/
│   └── test_recipe.py
└── ...
```

- `pytest` 기반
- DB mocking 및 요청 시나리오 테스트 구성 예정

---

## ✅ 기술 스택

| 구성     | 사용 기술                                         |
| ------ | --------------------------------------------- |
| API 서버 | FastAPI                                       |
| 인증     | JWT (jose)                                    |
| ORM    | SQLAlchemy                                    |
| DB     | MariaDB (auth, service), PostgreSQL (log, 추천) |
| 추천     | Word2Vec, BERT, FAISS                         |
| 배포     | Docker, Nginx, GitHub Actions                 |
| 클라우드   | AWS EC2 + S3 + RDS                            |

---

## 📌 향후 고려 사항

| 항목           | 설명                  |
| ------------ | ------------------- |
| Kafka 도입     | 사용자 로그의 실시간 스트리밍 처리 |
| Airflow 연동   | 추천 벡터 주기적 갱신 파이프라인  |
| 관리자 포털 추가    | 상품 및 사용자 관리 페이지 구성  |
| 유닛/통합 테스트 강화 | CI/CD 안정성 확보        |

---

## 📍 기타

| 항목       | 설명                                                  |
| -------- | --------------------------------------------------- |
| 포트 구성    | gateway: 8000, user: 8001, kok: 8002 등 서비스별 포트 분리   |
| CORS 설정  | `common/config.py` 또는 gateway에서 중앙 관리               |
| 환경 변수 관리 | `.env` 파일에서 서비스 공통 설정 로딩 (`SECRET_KEY`, `DB_URL` 등) |

---

## ☁️ 클라우드 고려사항 (AWS 기준)

| 항목               | 적용 예시                                           |
| ---------------- | ----------------------------------------------- |
| EC2              | FastAPI 앱, Nginx 리버스 프록시, Docker 기반 배포          |
| RDS              | MariaDB (user, service) / PostgreSQL (log, 추천용) |
| S3               | 추천 모델 파일(word2vec, BERT), 이미지, 크롤링 데이터 저장       |
| CloudWatch / ELK | 사용자 로그 분석/시각화 용도 (log-service 연계)               |
| GitHub Actions   | CI/CD + EC2 배포 자동화 (옵션)                         |

