# 파일 구조

```
backend/
├── common/
│   ├── auth/
│   │   └── jwt_handler.py                  # JWT 발급 및 검증
│   ├── config.py                           # settings 로딩 및 환경변수 관리
│   ├── dependencies.py                     # get_current_user 등 공통 Depends
│   ├── errors.py                           # 공통 예외 클래스
│   ├── logger.py                           # 공통 로거
│   ├── utils.py                            # now_str(), truncate_text 등
│   └── database/
│       ├── base_mariadb.py                # DeclarativeBase for MariaDB
│       ├── base_postgres.py               # DeclarativeBase for PostgreSQL
│       ├── mariadb_auth.py                # auth_db용 세션
│       ├── mariadb_service.py             # service_db용 세션
│       ├── postgres_log.py                # log_db용 세션
│       └── postgres_recommend.py          # recommend_db용 세션
│
├── gateway/
│   ├── main.py                             # FastAPI 앱 진입점 (라우터 포함)
│   ├── config.py                           # CORS 등 미들웨어
│   └── routes/
│       └── ...                             # (필요 시 라우팅 제어)
│
├── services/
│   ├── user/
│   │   ├── main.py
│   │   ├── routers/user_router.py
│   │   ├── models/user_model.py           # MariaBase 사용
│   │   ├── schemas/user_schema.py
│   │   └── crud/user_crud.py
│
│   ├── kok/
│   │   ├── main.py
│   │   ├── routers/kok_router.py
│   │   ├── models/
│   │   │   ├── product_model.py
│   │   │   └── recommend_model.py         # PostgresBase 사용
│   │   ├── schemas/kok_schema.py
│   │   └── crud/
│   │       ├── kok_crud.py
│   │       └── recommend_crud.py
│
│   ├── home_shopping/
│   │   ├── main.py
│   │   ├── routers/home_router.py
│   │   ├── models/show_model.py
│   │   ├── schemas/show_schema.py
│   │   └── crud/show_crud.py
│
│   ├── order/
│   │   ├── main.py
│   │   ├── routers/order_router.py
│   │   ├── models/order_model.py
│   │   ├── schemas/order_schema.py
│   │   └── crud/order_crud.py
│
│   ├── recipe/
│   │   ├── main.py
│   │   ├── routers/recipe_router.py
│   │   ├── models/
│   │   │   ├── recipe_model.py            # MariaBase
│   │   │   └── recommend_model.py         # PostgresBase
│   │   ├── schemas/recipe_schema.py
│   │   └── crud/
│   │       ├── base_crud.py
│   │       └── recommend_crud.py
│
│   ├── log/
│   │   ├── main.py
│   │   ├── routers/log_router.py
│   │   ├── models/log_model.py
│   │   ├── schemas/log_schema.py
│   │   └── crud/log_crud.py
│
│   └── recommend/
│       └── rankers/                        # 공통 추천 알고리즘 유틸
│           ├── bert_ranker.py
│           ├── word2vec_ranker.py
│           └── faiss_loader.py
│
├── requirements.txt                       # Python 의존성
├── .env                                   # DB URL 등 환경변수
└── README.md
```