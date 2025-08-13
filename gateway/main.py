"""
gateway/main.py
---------------
API Gateway 서비스 진입점.
각 서비스의 FastAPI router를 통합해서 전체 API 엔드포인트로 제공한다.
- CORS, 공통 예외처리, 로깅 등 공통 설정도 이곳에서 적용
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_settings
from common.logger import get_logger
from services.user.routers.user_router import router as user_router
from services.log.routers.log_router import router as log_router
from services.home_shopping.routers.home_shopping_router import router as home_shopping_router
from services.kok.routers.kok_router import router as kok_router
from services.order.routers.order_router import router as order_router
from services.order.routers.kok_order_router import router as kok_order_router
from services.recipe.routers.recipe_router import router as recipe_router

# TODO: 다른 서비스(router) import 추가 (recommend 등)

logger = get_logger("gateway")
logger.info("API Gateway 초기화 시작...")

try:
    settings = get_settings()
    logger.info("설정 로드 완료")
except Exception as e:
    logger.error(f"설정 로드 실패: {e}")
    raise

logger.info(f"FastAPI 애플리케이션 생성: 제목={settings.app_name}, 디버그={settings.debug}")

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)

# CORS 설정
logger.info("CORS 미들웨어 설정 중...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS 미들웨어 설정 완료")

# 라우터 등록 (각 서비스별 router를 include)
logger.info("서비스 라우터 등록 중...")

logger.debug("사용자 라우터 포함 중...")
app.include_router(user_router)
logger.info("사용자 라우터 포함 완료")

logger.debug("로그 라우터 포함 중...")
app.include_router(log_router)
logger.info("로그 라우터 포함 완료")

logger.debug("홈쇼핑 라우터 포함 중...")
app.include_router(home_shopping_router)
logger.info("홈쇼핑 라우터 포함 완료")

logger.debug("콕 라우터 포함 중...")
app.include_router(kok_router)
logger.info("콕 라우터 포함 완료")

logger.debug("주문 라우터 포함 중...")
app.include_router(order_router)
logger.info("주문 라우터 포함 완료")

logger.debug("콕 주문 라우터 포함 중...")
app.include_router(kok_order_router)
logger.info("콕 주문 라우터 포함 완료")

logger.debug("레시피 라우터 포함 중...")
app.include_router(recipe_router)
logger.info("레시피 라우터 포함 완료")

logger.info("API Gateway 시작 완료")    
logger.info(f"앱 제목: {settings.app_name}")
logger.info(f"디버그 모드: {settings.debug}")
logger.info("모든 서비스 라우터 등록 완료")

# TODO: 다른 서비스 라우터도 아래와 같이 추가
# from services.recommend.routers.recommend_router import router as recommend_router
# app.include_router(recommend_router)

# 공통 예외 처리 (필요시)
# from common.errors import *
# @app.exception_handler(...)
# async def custom_exception_handler(...):
#     ...

# if __name__ == "__main__":
#     uvicorn.run("gateway.main:app", host="0.0.0.0", port=8000, reload=True)