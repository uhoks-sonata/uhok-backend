"""
user 서비스 단독 실행용
"""
from fastapi import FastAPI  # FastAPI 메인 앱 객체 임포트
from services.user.routers import user_router  # user 관련 라우터 임포트
from services.user.database import Base, engine  # ORM Base, DB 엔진 임포트

app = FastAPI(title="User Service")  # FastAPI 앱 인스턴스 생성, 서비스명 지정

Base.metadata.create_all(bind=engine)  # DB에 ORM 모델에 해당하는 테이블 자동 생성

app.include_router(user_router.router)  # user 관련 API 라우터 등록
