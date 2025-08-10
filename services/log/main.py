"""
user 서비스 단독 실행용 (비동기 엔진 기반)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.log.routers import log_router
from common.logger import get_logger

logger = get_logger("log_service")

app = FastAPI(title="Log")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(log_router.router)

logger.info("Log Service initialized successfully")
logger.info("CORS middleware configured for localhost:3001")
logger.info("Log router included")
