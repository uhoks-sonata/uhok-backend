"""
order 서비스 단독 실행용 (비동기 엔진 기반)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.order.routers import order_router

app = FastAPI(title="Order Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(order_router.router, prefix="/api/orders", tags=["orders"])
