from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.likes_crud import (
    get_homeshopping_liked_products,
    toggle_homeshopping_likes,
)
from services.homeshopping.schemas.likes_schema import (
    HomeshoppingLikesResponse,
    HomeshoppingLikesToggleRequest,
    HomeshoppingLikesToggleResponse,
)
from services.user.schemas.profile_schema import UserOut

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()

@router.post("/likes/toggle", response_model=HomeshoppingLikesToggleResponse)
async def toggle_likes(
        request: Request,
        like_data: HomeshoppingLikesToggleRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 찜 등록/해제
    """
    logger.debug(f"홈쇼핑 찜 토글 시작: user_id={current_user.user_id}, live_id={like_data.live_id}")
    logger.info(f"홈쇼핑 찜 토글 요청: user_id={current_user.user_id}, live_id={like_data.live_id}")
    
    try:
        liked = await toggle_homeshopping_likes(db, current_user.user_id, like_data.live_id)
        await db.commit()
        logger.debug(f"찜 토글 성공: user_id={current_user.user_id}, live_id={like_data.live_id}, liked={liked}")
        
        # 찜 토글 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_likes_toggle", 
                event_data={"live_id": like_data.live_id, "liked": liked},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        message = "찜이 등록되었습니다." if liked else "찜이 해제되었습니다."
        logger.info(f"홈쇼핑 찜 토글 완료: user_id={current_user.user_id}, live_id={like_data.live_id}, liked={liked}")
        
        return {
            "liked": liked,
            "message": message
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 찜 토글 실패: user_id={current_user.user_id}, live_id={like_data.live_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜 토글 중 오류가 발생했습니다.")


@router.get("/likes", response_model=HomeshoppingLikesResponse)
async def get_liked_products(
        request: Request,
        limit: int = Query(50, ge=1, le=100, description="조회할 찜한 상품 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 찜한 상품 목록 조회
    """
    logger.debug(f"홈쇼핑 찜한 상품 조회 시작: user_id={current_user.user_id}, limit={limit}")
    logger.info(f"홈쇼핑 찜한 상품 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    try:
        liked_products = await get_homeshopping_liked_products(db, current_user.user_id, limit)
        logger.debug(f"찜한 상품 조회 성공: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    except Exception as e:
        logger.error(f"찜한 상품 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜한 상품 조회 중 오류가 발생했습니다.")
    
    # 찜한 상품 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_liked_products_view", 
            event_data={"liked_products_count": len(liked_products)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    return {"liked_products": liked_products}

