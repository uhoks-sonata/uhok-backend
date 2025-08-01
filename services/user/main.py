"""
user 서비스 단독 실행용 (비동기 엔진 기반)
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from services.user.routers import user_router
import traceback
from fastapi.middleware.cors import CORSMiddleware
from services.user.database import Base, engine
import asyncio

app = FastAPI(title="User Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router, prefix="/api/user", tags=["user"])

# # 비동기 엔진에서 테이블 자동생성 (로컬/테스트 용도, 운영에서는 Alembic 권장)
# async def init_models():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#
# @app.on_event("startup")
# async def on_startup():
#     await init_models()

print("#### TEST MAIN.PY TOP ####")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    print(f"Response status: {response.status_code}")
    return response

@app.api_route("/{catchall:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request):
    print(f"Catch-all triggered for: {request.method} {request.url}")
    return JSONResponse(content={"msg": "Catch-all reached!"})

@app.exception_handler(Exception)
async def catch_all_exceptions(request: Request, exc: Exception):
    print("=== [Global Exception] ===")
    print(repr(exc))
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error (global handler)", "msg": str(exc)},
    )

@app.get("/__alive__")
def alive():
    print("ALIVE ENDPOINT CALLED")
    return {"msg": "alive"}

@app.get("/logtest")
def logtest():
    print("=== /logtest endpoint called ===")
    return {"msg": "logtest ok"}

print("#### TEST MAIN.PY BOTTOM ####")
