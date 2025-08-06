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
from common.logger import logger
from services.user.routers.user_router import router as user_router
from services.recipe.routers.recipe_router import router as recipe_router
from services.kok.routers.kok_router import router as kok_router
from services.order.routers.order_router import router as order_router
from services.log.routers.log_router import router as log_router
from services.home_shopping.routers.home_shopping_router import router as home_shopping_router

# TODO: 다른 서비스(router) import 추가 (recommend 등)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록 (각 서비스별 router를 include)
app.include_router(user_router)
app.include_router(recipe_router)
app.include_router(kok_router)
app.include_router(order_router)
app.include_router(log_router)
app.include_router(home_shopping_router)


# TODO: 다른 서비스 라우터도 아래와 같이 추가
# from services.recommend.routers.recommend_router import router as recommend_router
# app.include_router(recommend_router, prefix="/api/recommend")

# 공통 예외 처리 (필요시)
# from common.errors import *
# @app.exception_handler(...)
# async def custom_exception_handler(...):
#     ...


# if __name__ == "__main__":
#     uvicorn.run("gateway.main:app", host="0.0.0.0", port=8000, reload=True)