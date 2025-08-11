"""
홈쇼핑 서비스 단독 실행용 (비동기 엔진 기반)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.home_shopping.routers.home_shopping_router import router as home_shopping_router
from common.logger import get_logger

logger = get_logger("home_shopping_service")

app = FastAPI(title="Home Shopping Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 홈쇼핑 라우터 등록
app.include_router(home_shopping_router)

logger.info("홈쇼핑 서비스 초기화 완료")
