"""
홈쇼핑 API 라우터 (MariaDB)
- 편성표 조회, 상품 검색, 찜 기능, 주문 등 홈쇼핑 관련 기능
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user
from services.user.schemas.user_schema import UserOut
from services.home_shopping.schemas.home_shopping_schema import (
    # 편성표 관련 스키마
    HomeshoppingScheduleResponse,
    
    # 상품 검색 관련 스키마
    HomeshoppingSearchRequest,
    HomeshoppingSearchResponse,
    
    # 검색 이력 관련 스키마
    HomeshoppingSearchHistoryCreate,
    HomeshoppingSearchHistoryResponse,
    HomeshoppingSearchHistoryDeleteRequest,
    HomeshoppingSearchHistoryDeleteResponse,
    
    # 상품 상세 관련 스키마
    HomeshoppingProductDetailResponse,
    
    # 상품 추천 관련 스키마
    HomeshoppingProductRecommendationsResponse,
    
    # 주문 관련 스키마
    HomeshoppingOrderRequest,
    HomeshoppingOrderResponse,
    
    # 스트리밍 관련 스키마
    HomeshoppingStreamResponse,
    
    # 찜 관련 스키마
    HomeshoppingLikesToggleRequest,
    HomeshoppingLikesToggleResponse,
    HomeshoppingLikesResponse,
    
    # 알림 관련 스키마
    HomeshoppingNotificationHistoryResponse
)

from services.home_shopping.crud.home_shopping_crud import (
    # 편성표 관련 CRUD
    get_homeshopping_schedule,
    
    # 상품 검색 관련 CRUD
    search_homeshopping_products,
    
    # 검색 이력 관련 CRUD
    add_homeshopping_search_history,
    get_homeshopping_search_history,
    delete_homeshopping_search_history,
    
    # 상품 상세 관련 CRUD
    get_homeshopping_product_detail,
    
    # 상품 추천 관련 CRUD
    get_homeshopping_product_recommendations,
    
    # 주문 관련 CRUD
    create_homeshopping_order,
    
    # 스트리밍 관련 CRUD
    get_homeshopping_stream_info,
    
    # 찜 관련 CRUD
    toggle_homeshopping_likes,
    get_homeshopping_liked_products,
    
    # 알림 관련 CRUD
    get_homeshopping_notifications_history
)

from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.logger import get_logger

router = APIRouter(prefix="/api/homeshopping", tags=["HomeShopping"])
logger = get_logger("home_shopping_router")


# ================================
# 편성표 관련 API
# ================================

@router.get("/schedule", response_model=HomeshoppingScheduleResponse)
async def get_schedule(
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 편성표 조회
    """
    logger.info(f"홈쇼핑 편성표 조회 요청: user_id={current_user.user_id}, page={page}, size={size}")
    
    schedules = await get_homeshopping_schedule(db, page=page, size=size)
    
    # 편성표 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_schedule_view", 
            event_data={"page": page, "size": size}
        )
    
    logger.info(f"홈쇼핑 편성표 조회 완료: user_id={current_user.user_id}, 결과 수={len(schedules)}")
    return {"schedules": schedules}


# ================================
# 상품 검색 관련 API
# ================================

@router.get("/search", response_model=HomeshoppingSearchResponse)
async def search_products(
        keyword: str = Query(..., description="검색 키워드"),
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 검색
    """
    logger.info(f"홈쇼핑 상품 검색 요청: user_id={current_user.user_id}, keyword='{keyword}', page={page}, size={size}")
    
    products, total = await search_homeshopping_products(db, keyword, page, size)
    
    # 검색 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search", 
            event_data={"keyword": keyword, "page": page, "size": size, "total": total}
        )
    
    logger.info(f"홈쇼핑 상품 검색 완료: user_id={current_user.user_id}, keyword='{keyword}', 결과 수={len(products)}")
    return {
        "total": total,
        "page": page,
        "size": size,
        "products": products
    }


# ================================
# 검색 이력 관련 API
# ================================

@router.post("/search/history", response_model=dict)
async def add_search_history(
        search_data: HomeshoppingSearchHistoryCreate,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 저장
    """
    logger.info(f"홈쇼핑 검색 이력 저장 요청: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    
    saved_history = await add_homeshopping_search_history(db, current_user.user_id, search_data.keyword)
    
    # 검색 이력 저장 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search_history_save", 
            event_data={"keyword": search_data.keyword}
        )
    
    logger.info(f"홈쇼핑 검색 이력 저장 완료: user_id={current_user.user_id}, history_id={saved_history['homeshopping_history_id']}")
    return saved_history


@router.get("/search/history", response_model=HomeshoppingSearchHistoryResponse)
async def get_search_history(
        limit: int = Query(5, ge=1, le=20, description="조회할 검색 이력 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 조회
    """
    logger.info(f"홈쇼핑 검색 이력 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    history = await get_homeshopping_search_history(db, current_user.user_id, limit)
    
    # 검색 이력 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search_history_view", 
            event_data={"history_count": len(history)}
        )
    
    logger.info(f"홈쇼핑 검색 이력 조회 완료: user_id={current_user.user_id}, 결과 수={len(history)}")
    return {"history": history}


@router.delete("/search/history", response_model=HomeshoppingSearchHistoryDeleteResponse)
async def delete_search_history(
        delete_data: HomeshoppingSearchHistoryDeleteRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 삭제
    """
    logger.info(f"홈쇼핑 검색 이력 삭제 요청: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
    
    success = await delete_homeshopping_search_history(db, current_user.user_id, delete_data.homeshopping_history_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 검색 이력을 찾을 수 없습니다.")
    
    # 검색 이력 삭제 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search_history_delete", 
            event_data={"history_id": delete_data.homeshopping_history_id}
        )
    
    logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
    return {"message": "검색 이력이 삭제되었습니다."}


# ================================
# 상품 상세 관련 API
# ================================

@router.get("/product/{product_id}", response_model=HomeshoppingProductDetailResponse)
async def get_product_detail(
        product_id: str,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 상세 조회
    """
    logger.info(f"홈쇼핑 상품 상세 조회 요청: user_id={current_user.user_id}, product_id={product_id}")
    
    product_detail = await get_homeshopping_product_detail(db, product_id, current_user.user_id)
    if not product_detail:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    # 상품 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_product_detail_view", 
            event_data={"product_id": product_id}
        )
    
    logger.info(f"홈쇼핑 상품 상세 조회 완료: user_id={current_user.user_id}, product_id={product_id}")
    return product_detail


# ================================
# 상품 추천 관련 API
# ================================

@router.get("/product/{product_id}/recommendations", response_model=HomeshoppingProductRecommendationsResponse)
async def get_product_recommendations(
        product_id: str,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 추천 조회
    """
    logger.info(f"홈쇼핑 상품 추천 조회 요청: user_id={current_user.user_id}, product_id={product_id}")
    
    recommendations = await get_homeshopping_product_recommendations(db, product_id)
    
    # 상품 추천 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_product_recommendations_view", 
            event_data={"product_id": product_id, "recommendations_count": len(recommendations)}
        )
    
    logger.info(f"홈쇼핑 상품 추천 조회 완료: user_id={current_user.user_id}, product_id={product_id}, 추천 수={len(recommendations)}")
    return {"recommendations": recommendations}

# ================================
# 스트리밍 관련 API
# ================================

@router.get("/product/{product_id}/stream", response_model=HomeshoppingStreamResponse)
async def get_stream_info(
        product_id: str,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 라이브 영상 URL 조회
    """
    logger.info(f"홈쇼핑 스트리밍 정보 조회 요청: user_id={current_user.user_id}, product_id={product_id}")
    
    stream_info = await get_homeshopping_stream_info(db, product_id)
    if not stream_info:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    # 스트리밍 정보 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_stream_info_view", 
            event_data={"product_id": product_id, "is_live": stream_info["is_live"]}
        )
    
    logger.info(f"홈쇼핑 스트리밍 정보 조회 완료: user_id={current_user.user_id}, product_id={product_id}")
    return stream_info


# ================================
# 찜 관련 API
# ================================

@router.post("/likes/toggle", response_model=HomeshoppingLikesToggleResponse)
async def toggle_likes(
        like_data: HomeshoppingLikesToggleRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 찜 등록/해제
    """
    logger.info(f"홈쇼핑 찜 토글 요청: user_id={current_user.user_id}, product_id={like_data.product_id}")
    
    liked = await toggle_homeshopping_likes(db, current_user.user_id, like_data.product_id)
    
    # 찜 토글 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_likes_toggle", 
            event_data={"product_id": like_data.product_id, "liked": liked}
        )
    
    message = "찜이 등록되었습니다." if liked else "찜이 해제되었습니다."
    logger.info(f"홈쇼핑 찜 토글 완료: user_id={current_user.user_id}, product_id={like_data.product_id}, liked={liked}")
    
    return {
        "liked": liked,
        "message": message
    }


@router.get("/likes", response_model=HomeshoppingLikesResponse)
async def get_liked_products(
        limit: int = Query(50, ge=1, le=100, description="조회할 찜한 상품 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 찜한 상품 목록 조회
    """
    logger.info(f"홈쇼핑 찜한 상품 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    liked_products = await get_homeshopping_liked_products(db, current_user.user_id, limit)
    
    # 찜한 상품 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_liked_products_view", 
            event_data={"liked_products_count": len(liked_products)}
        )
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    return {"liked_products": liked_products}


# ================================
# 주문 관련 API
# ================================

@router.post("/order", response_model=HomeshoppingOrderResponse)
async def create_order(
        order_data: HomeshoppingOrderRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 생성
    """
    logger.info(f"홈쇼핑 주문 생성 요청: user_id={current_user.user_id}, items_count={len(order_data.items)}")
    
    order_result = await create_homeshopping_order(
        db, 
        current_user.user_id, 
        [{"product_id": item.product_id, "quantity": item.quantity} for item in order_data.items],
        order_data.delivery_address,
        order_data.delivery_phone
    )
    
    # 주문 생성 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_order_create", 
            event_data={"order_id": order_result["order_id"], "items_count": len(order_data.items)}
        )
    
    logger.info(f"홈쇼핑 주문 생성 완료: user_id={current_user.user_id}, order_id={order_result['order_id']}")
    return order_result


# ================================
# 알림 관련 API
# ================================

@router.get("/notifications/history", response_model=HomeshoppingNotificationHistoryResponse)
async def get_notifications_history(
        limit: int = Query(20, ge=1, le=100, description="조회할 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 알림 내역 조회
    """
    logger.info(f"홈쇼핑 알림 내역 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_homeshopping_notifications_history(
            db, current_user.user_id, limit, offset
        )
        
        # 알림 내역 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_notifications_history_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 알림 내역 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        return {
            "notifications": notifications,
            "total_count": total_count
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 알림 내역 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="알림 내역 조회 중 오류가 발생했습니다.")
