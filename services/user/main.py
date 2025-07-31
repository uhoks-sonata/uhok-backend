"""
user 서비스 단독 실행용
"""
from fastapi import FastAPI
from services.user.routers import user_router
from services.user.database import Base, engine

app = FastAPI(title="User Service")
Base.metadata.create_all(bind=engine)

app.include_router(user_router.router)
