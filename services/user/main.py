"""
user 서비스 단독 실행용 (비동기 엔진 기반)
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import traceback

from services.user.routers import user_router
from common.logger import get_logger

logger = get_logger("user_service")

app = FastAPI(title="User Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router)

# # 비동기 엔진에서 테이블 자동생성 (로컬/테스트 용도, 운영에서는 Alembic 권장)
# async def init_models():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#
# @app.on_event("startup")
# async def on_startup():
#     await init_models()

logger.info("#### TEST MAIN.PY TOP ####")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response


@app.exception_handler(Exception)
async def catch_all_exceptions(request: Request, exc: Exception):
    logger.error("=== [Global Exception] ===")
    logger.error(f"Exception: {repr(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error (global handler)", "msg": str(exc)},
    )


@app.get("/logtest")
def logtest():
    logger.info("=== /logtest endpoint called ===")
    return {"msg": "logtest ok"}
