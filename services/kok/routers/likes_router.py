from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.user.schemas.profile_schema import UserOut
from services.kok.schemas.interaction_schema import (
    KokLikesToggleRequest,
    KokLikesToggleResponse,
    KokLikedProductsResponse,
)
from services.kok.crud.likes_crud import (
    toggle_kok_likes,
    get_kok_liked_products,
)

logger = get_logger("kok_router")
router = APIRouter()

@router.post("/likes/toggle", response_model=KokLikesToggleResponse)
async def toggle_likes(
    request: Request,
    like_data: KokLikesToggleRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 찜 등록/해제
    """
    logger.debug(f"찜 토글 시작: user_id={current_user.user_id}, kok_product_id={like_data.kok_product_id}")
    logger.info(f"찜 토글 요청: user_id={current_user.user_id}, kok_product_id={like_data.kok_product_id}")
    
    try:
        liked = await toggle_kok_likes(db, current_user.user_id, like_data.kok_product_id)
        await db.commit()
        logger.debug(f"찜 토글 성공: user_id={current_user.user_id}, kok_product_id={like_data.kok_product_id}, liked={liked}")
        logger.info(f"찜 토글 완료: user_id={current_user.user_id}, kok_product_id={like_data.kok_product_id}, liked={liked}")
        
        # 찜 토글 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_likes_toggle", 
                event_data={
                    "kok_product_id": like_data.kok_product_id,
                    "liked": liked
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        if liked:
            return {
                "liked": True,
                "message": "상품을 찜했습니다."
            }
        else:
            return {
                "liked": False,
                "message": "찜이 취소되었습니다."
            }
    except Exception as e:
        await db.rollback()
        logger.error(f"찜 토글 실패: user_id={current_user.user_id}, kok_product_id={like_data.kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜 토글 중 오류가 발생했습니다.")


@router.get("/likes", response_model=KokLikedProductsResponse)
async def get_liked_products(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="조회할 찜 상품 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    찜한 상품 목록 조회
    """
    logger.debug(f"찜한 상품 목록 조회 시작: user_id={current_user.user_id}, limit={limit}")
    
    try:
        liked_products = await get_kok_liked_products(db, current_user.user_id, limit)
        logger.debug(f"찜한 상품 목록 조회 성공: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    except Exception as e:
        logger.error(f"찜한 상품 목록 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜한 상품 목록 조회 중 오류가 발생했습니다.")
    
    # 찜한 상품 목록 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_liked_products_view", 
            event_data={
                "limit": limit,
                "product_count": len(liked_products)
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"liked_products": liked_products}
