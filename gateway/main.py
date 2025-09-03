"""
gateway/main.py
---------------
API Gateway 서비스 진입점.
각 서비스의 FastAPI router를 통합해서 전체 API 엔드포인트로 제공한다.
- CORS, 공통 예외처리, 로깅 등 공통 설정도 이곳에서 적용
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from common.config import get_settings
from common.logger import get_logger
# from common.http_log_middleware import HttpLogMiddleware  # 미들웨어 비활성화
from services.user.routers.user_router import router as user_router
from services.log.routers.user_event_log_router import router as user_event_log_router
from services.log.routers.user_activity_log_routers import router as user_activity_log_router
from services.order.routers.order_router import router as order_router
from services.order.routers.payment_router import router as payment_router
from services.homeshopping.routers.homeshopping_router import router as homeshopping_router
from services.order.routers.hs_order_router import router as hs_order_router
from services.kok.routers.kok_router import router as kok_router
from services.order.routers.kok_order_router import router as kok_order_router
from services.recipe.routers.recipe_router import router as recipe_router

logger = get_logger("gateway", sqlalchemy_logging={'enable': False})
logger.info("API Gateway 초기화 시작...")

try:
    settings = get_settings()
    logger.info("설정 로드 완료")
    
    # 현재 환경 정보 출력
    logger.info(f"현재 환경: DEBUG={settings.debug}")
    
    # uvicorn 액세스 로그 완전 비활성화 (개발/운영 구분 없이)
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    
    logger.info("Uvicorn 액세스 로그 비활성화 완료")
    
except Exception as e:
    logger.error(f"설정 로드 실패: {e}")
    raise

logger.info(f"FastAPI 애플리케이션 생성: 제목={settings.app_name}, 디버그={settings.debug}")

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)

# HTTP 로깅 미들웨어 설정 (비활성화 - 라우터에서만 로깅)
# logger.info("HTTP 로깅 미들웨어 설정 중...")
# app.add_middleware(HttpLogMiddleware)
# logger.info("HTTP 로깅 미들웨어 설정 완료")

# CORS 설정
logger.info("CORS 미들웨어 설정 중...")
app.add_middleware(            
    CORSMiddleware,
    allow_origins=[
        # 로컬 개발 환경
        "http://localhost:3001",      # React 포트
        "http://localhost:9001",      # FastAPI 포트
        "http://localhost:8501",      # Streamlit 포트
        
        # hosts 파일에 등록한 alias (팀원별)
        "http://webapp.uhok.com:3001", # 프론트엔드 1
        "http://webapp2.uhok.com:3001", # 프론트엔드 2

        "http://api.uhok.com:9000", # 백엔드 1
        "http://api2.uhok.com:9000", # 백엔드 2

        "http://payment.uhok.com:9001", # 결제서버
    ],
    allow_credentials=True,  # 쿠키/인증 헤더 허용
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS 미들웨어 설정 완료")

logger.info("서비스 라우터 등록 중...")

logger.debug("사용자 라우터 포함 중...")
app.include_router(user_router)
logger.info("사용자 라우터 포함 완료")

logger.debug("로그 라우터 포함 중...")
app.include_router(user_event_log_router)
logger.info("로그 라우터 포함 완료")

logger.debug("활동 로그 라우터 포함 중...")
app.include_router(user_activity_log_router)
logger.info("활동 로그 라우터 포함 완료")

logger.debug("주문 라우터 포함 중...")
app.include_router(order_router)
logger.info("주문 라우터 포함 완료")

logger.debug("결제 라우터 포함 중...")
app.include_router(payment_router)
logger.info("결제 라우터 포함 완료")

# """홈쇼핑 정적파일 서빙
# - /homeshopping/static 경로로 JS/CSS/이미지 제공
# - 운영 시 Nginx로 오프로드하더라도 경로는 동일하게 유지 가능
# """
HS_STATIC_DIR = Path(__file__).resolve().parents[1] / "services" / "homeshopping" / "static"
app.mount("/homeshopping/static", StaticFiles(directory=str(HS_STATIC_DIR)), name="homeshopping-static")
logger.debug("홈쇼핑 라우터 포함 중...")
app.include_router(homeshopping_router)
logger.info("홈쇼핑 라우터 포함 완료")

logger.debug("홈쇼핑 주문 라우터 포함 중...")
app.include_router(hs_order_router)
logger.info("홈쇼핑 주문 라우터 포함 완료")

logger.debug("콕 라우터 포함 중...")
app.include_router(kok_router)
logger.info("콕 라우터 포함 완료")

logger.debug("콕 주문 라우터 포함 중...")
app.include_router(kok_order_router)
logger.info("콕 주문 라우터 포함 완료")

logger.debug("레시피 라우터 포함 중...")
app.include_router(recipe_router)
logger.info("레시피 라우터 포함 완료")

logger.info("모든 서비스 라우터 등록 완료")
logger.info("API Gateway 시작 완료")    


@app.get("/healthz")
async def healthz():
    """
    서비스 헬스체크 엔드포인트.
    - 컨테이너/오케스트레이션의 상태 점검용으로 사용
    - DB 연결까지 점검하려면 간단 쿼리를 추가해서 True/False 반환하도록 확장 가능
    """
    return {"status": "ok"}

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