from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.jwt_handler import verify_token
from common.errors import InvalidTokenException, NotFoundException
from services.user.crud.user_crud import get_user_by_id
from services.user.crud.jwt_blacklist_crud import is_token_blacklisted
from services.user.schemas.user_schema import UserOut

from common.database.mariadb_auth import get_maria_auth_db
from common.logger import get_logger

from typing import Optional

from common.config import get_settings
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")
logger = get_logger("dependencies")

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession  = Depends(get_maria_auth_db),
) -> UserOut:
    """토큰 기반 사용자 인증 후 유저 정보 반환"""
    try:
        # logger.debug(f"Token verification started: {token[:10]}...")
        
        payload = verify_token(token)
        if payload is None:
            logger.warning("토큰 검증 실패: 유효하지 않은 토큰")
            raise InvalidTokenException()

        # 토큰이 블랙리스트에 있는지 확인
        if await is_token_blacklisted(db, token):
            logger.warning(f"토큰이 블랙리스트에 등록됨: {token[:10]}...")
            raise InvalidTokenException("로그아웃된 토큰입니다.")

        user_id_raw = payload.get("sub")
        if not user_id_raw:
            logger.warning("토큰 페이로드에 사용자 ID 누락")
            raise InvalidTokenException("토큰에 사용자 정보가 없습니다.")
        
        try:
            user_id = int(user_id_raw)
        except (ValueError, TypeError):
            logger.error(f"토큰의 사용자 ID가 유효하지 않음: {user_id_raw}")
            raise InvalidTokenException("토큰의 사용자 ID가 유효하지 않습니다.")

        user = await get_user_by_id(db, user_id)
        if user is None:
            logger.warning(f"사용자를 찾을 수 없음: user_id={user_id}")
            raise NotFoundException("사용자")

        # SQLAlchemy ORM 객체를 Pydantic 모델로 변환하여 직렬화 문제 해결
        from services.user.schemas.user_schema import UserOut
        user_out = UserOut(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            created_at=user.created_at
        )

        logger.debug(f"사용자 인증 성공: user_id={user_id}")
        return user_out
        
    except Exception as e:
        logger.error(f"인증 실패: {str(e)}")
        logger.error(f"인증 실패 상세: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        raise


async def get_current_user_optional(
    request: Request
) -> Optional[UserOut]:
    """인증이 실패해도 에러를 발생시키지 않는 선택적 사용자 의존성"""
    authorization = request.headers.get("authorization")
    
    # 디버깅 로그 추가
    logger.info(f"Authorization 헤더: {authorization}")
    
    if not authorization:
        logger.info("Authorization 헤더가 없습니다.")
        return None
    
    try:
        # JWT 토큰에서 사용자 ID 추출
        from common.auth.jwt_handler import verify_token
        
        # Bearer 토큰에서 실제 토큰 추출
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            logger.info(f"Bearer 토큰 추출: {token[:20]}...")
        else:
            token = authorization
            logger.info(f"직접 토큰: {token[:20]}...")
        
        # JWT 토큰 검증 전 로그
        logger.info(f"verify_token 호출 전 토큰 길이: {len(token)}")
        logger.info(f"토큰의 처음 50자: {token[:50]}")
        
        # JWT 토큰 검증
        payload = verify_token(token)
        logger.info(f"verify_token 결과: {payload}")
        
        if not payload:
            logger.warning("JWT 페이로드가 없습니다.")
            # 추가 디버깅: 직접 JWT 디코딩 시도
            try:
                from jose import jwt
                from common.config import get_settings
                settings = get_settings()
                logger.info(f"JWT 시크릿: {settings.jwt_secret[:10]}...")
                logger.info(f"JWT 알고리즘: {settings.jwt_algorithm}")
                
                # 직접 디코딩 시도
                direct_payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
                logger.info(f"직접 디코딩 결과: {direct_payload}")
            except Exception as direct_error:
                logger.error(f"직접 디코딩 실패: {str(direct_error)}")
            
            return None
        
        user_id_raw = payload.get("sub")
        if not user_id_raw:
            logger.warning("user_id가 유효하지 않습니다.")
            return None
        
        try:
            user_id = int(user_id_raw)
            logger.info(f"추출된 user_id: {user_id}")
        except (ValueError, TypeError):
            logger.error(f"토큰의 사용자 ID가 유효하지 않음: {user_id_raw}")
            return None
        
        # 데이터베이스에서 실제 사용자 정보 조회
        # 직접 데이터베이스 연결을 생성하여 사용자 정보 조회
        from common.database.mariadb_auth import engine, SessionLocal
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # 새로운 세션 생성
        async with SessionLocal() as db:
            user = await get_user_by_id(db, user_id)
            if user is None:
                logger.warning(f"사용자를 찾을 수 없음: user_id={user_id}")
                return None
            
            # SQLAlchemy ORM 객체를 Pydantic 모델로 변환
            user_out = UserOut(
                user_id=user.user_id,
                username=user.username,
                email=user.email,
                created_at=user.created_at
            )
            logger.info(f"사용자 객체 생성 완료: {user_out}")
            return user_out
        
    except Exception as e:
        # 인증 실패 시 None 반환 (에러 발생하지 않음)
        logger.error(f"JWT 토큰 처리 중 오류 발생: {str(e)}")
        return None


async def debug_optional_auth(request: Request, endpoint_name: str):
    """선택적 인증 디버깅을 위한 공통 함수"""
    logger.info(f"=== {endpoint_name} 디버깅 시작 ===")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Authorization header: {request.headers.get('authorization')}")
    
    current_user = await get_current_user_optional(request)
    logger.info(f"get_current_user_optional 결과: {current_user}")
    
    user_id = current_user.user_id if current_user else None
    logger.info(f"최종 user_id: {user_id}")
    logger.info(f"=== {endpoint_name} 디버깅 완료 ===")
    
    return current_user, user_id
