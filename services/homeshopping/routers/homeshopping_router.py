"""
홈쇼핑 API 라우터 (MariaDB)
- 편성표 조회, 상품 검색, 찜 기능, 주문 등 홈쇼핑 관련 기능
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user, get_current_user_optional

from services.user.schemas.user_schema import UserOut
from services.homeshopping.schemas.homeshopping_schema import (
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
    
    # 레시피 추천 관련 스키마
    RecipeRecommendationsResponse,
    
    # 스트리밍 관련 스키마
    HomeshoppingStreamResponse,
    
    # 찜 관련 스키마
    HomeshoppingLikesToggleRequest,
    HomeshoppingLikesToggleResponse,
    HomeshoppingLikesResponse,
    
    # 통합 알림 관련 스키마 (기존 테이블 활용)
    HomeshoppingNotificationListResponse,
    HomeshoppingNotificationFilter,
    HomeshoppingNotificationUpdate
)

from services.homeshopping.crud.homeshopping_crud import (
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
    
    # 상품 분류 관련 CRUD
    get_homeshopping_classify_cls_ing,
    
    # 스트리밍 관련 CRUD
    get_homeshopping_stream_info,
    
    # 찜 관련 CRUD
    toggle_homeshopping_likes,
    get_homeshopping_liked_products,
    
    # 통합 알림 관련 CRUD (기존 테이블 활용)
    get_notifications_with_filter,
    mark_notification_as_read
)

from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.logger import get_logger

router = APIRouter(prefix="/api/homeshopping", tags=["HomeShopping"])
logger = get_logger("homeshopping_router")


# ================================
# 편성표 관련 API
# ================================

@router.get("/schedule", response_model=HomeshoppingScheduleResponse)
async def get_schedule(
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 편성표 조회 (식품만)
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 편성표 조회 요청: user_id={user_id}, page={page}, size={size}")
    
    schedules = await get_homeshopping_schedule(db, page=page, size=size)
    
    # 편성표 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_schedule_view", 
            event_data={"page": page, "size": size}
        )
    
    logger.info(f"홈쇼핑 편성표 조회 완료: user_id={user_id}, 결과 수={len(schedules)}")
    return {"schedules": schedules}

# ================================
# 상품 상세 관련 API
# ================================

@router.get("/product/{product_id}", response_model=HomeshoppingProductDetailResponse)
async def get_product_detail(
        product_id: int,
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 상세 조회
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 상세 조회 요청: user_id={user_id}, product_id={product_id}")
    
    product_detail = await get_homeshopping_product_detail(db, product_id, user_id)
    if not product_detail:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    # 상품 상세 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_product_detail_view", 
            event_data={"product_id": product_id}
        )
    
    logger.info(f"홈쇼핑 상품 상세 조회 완료: user_id={user_id}, product_id={product_id}")
    return product_detail


# ================================
# 상품 추천 관련 API
# ================================

@router.get("/product/{product_id}/kok-recommendations")
async def get_kok_recommendations(
    product_id: int,
    current_user: UserOut = Depends(get_current_user_optional),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품에 대한 콕 유사 상품 추천 조회
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 콕 유사 상품 추천 조회 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # 추천 오케스트레이터 호출 (통합된 CRUD에서)
        from services.homeshopping.crud.homeshopping_crud import recommend_homeshopping_to_kok
        
        recommendations = await recommend_homeshopping_to_kok(
            db=db,
            product_id=product_id,
            k=5,  # 최대 5개
            use_rerank=False
        )
        
        logger.info(f"홈쇼핑 콕 유사 상품 추천 조회 완료: user_id={user_id}, product_id={product_id}, 결과 수={len(recommendations)}")
        return {"products": recommendations}
        
    except Exception as e:
        logger.error(f"홈쇼핑 콕 유사 상품 추천 조회 실패: product_id={product_id}, error={str(e)}")
        
        # 폴백: 간단한 추천 시스템 사용 (통합된 CRUD에서)
        try:
            from services.homeshopping.crud.homeshopping_crud import simple_recommend_homeshopping_to_kok
            fallback_recommendations = await simple_recommend_homeshopping_to_kok(
                product_id=product_id,
                k=5,
                db=db  # DB 전달하여 실제 DB 연동 시도
            )
            logger.info(f"폴백 추천 시스템 사용: {len(fallback_recommendations)}개 상품")
            return {"products": fallback_recommendations}
        except Exception as fallback_error:
            logger.error(f"폴백 추천 시스템도 실패: {str(fallback_error)}")
            # 최종 폴백: 빈 배열 반환
            return {"products": []}


@router.get("/product/{product_id}/check")
async def check_product_ingredient(
        product_id: int,
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품의 식재료 여부 확인
    CLS_ING가 1(식재료)인지 여부만 확인
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 식재료 여부 확인 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 확인
        cls_ing = await get_homeshopping_classify_cls_ing(db, product_id)
        
        if cls_ing == 1:
            # 식재료인 경우
            logger.info(f"홈쇼핑 상품 식재료 확인 완료: product_id={product_id}, cls_ing={cls_ing}")
            return {"is_ingredient": True}
        else:
            # 완제품인 경우
            logger.info(f"홈쇼핑 완제품으로 식재료 아님: product_id={product_id}, cls_ing={cls_ing}")
            return {"is_ingredient": False}
            
    except Exception as e:
        logger.error(f"홈쇼핑 상품 식재료 여부 확인 실패: product_id={product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 식재료 여부 확인 중 오류가 발생했습니다.")

# ================================
# 스트리밍 관련 API
# ================================

@router.get("/product/{product_id}/stream", response_model=HomeshoppingStreamResponse)
async def get_stream_info(
        product_id: int,
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 라이브 영상 URL 조회
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 스트리밍 정보 조회 요청: user_id={user_id}, product_id={product_id}")
    
    stream_info = await get_homeshopping_stream_info(db, product_id)
    if not stream_info:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    # 스트리밍 정보 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_stream_info_view", 
            event_data={"product_id": product_id, "is_live": stream_info["is_live"]}
        )
    
    logger.info(f"홈쇼핑 스트리밍 정보 조회 완료: user_id={user_id}, product_id={product_id}")
    return stream_info


# ================================
# 상품 검색 관련 API
# ================================

@router.get("/search", response_model=HomeshoppingSearchResponse)
async def search_products(
        keyword: str = Query(..., description="검색 키워드"),
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 검색
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 검색 요청: user_id={user_id}, keyword='{keyword}', page={page}, size={size}")
    
    products, total = await search_homeshopping_products(db, keyword, page, size)
    
    # 검색 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search", 
            event_data={"keyword": keyword, "page": page, "size": size, "total": total}
        )
    
    logger.info(f"홈쇼핑 상품 검색 완료: user_id={user_id}, keyword='{keyword}', 결과 수={len(products)}")
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
# 통합 알림 관련 API
# ================================

@router.get("/notifications/orders", response_model=HomeshoppingNotificationListResponse)
async def get_order_notifications_api(
        limit: int = Query(20, ge=1, le=100, description="조회할 주문 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 상태 변경 알림만 조회
    """
    logger.info(f"홈쇼핑 주문 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="order_status",
            limit=limit, 
            offset=offset
        )
        
        # 주문 알림 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 주문 알림 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 주문 알림 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 알림 조회 중 오류가 발생했습니다.")


@router.get("/notifications/broadcasts", response_model=HomeshoppingNotificationListResponse)
async def get_broadcast_notifications_api(
        limit: int = Query(20, ge=1, le=100, description="조회할 방송 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 방송 시작 알림만 조회
    """
    logger.info(f"홈쇼핑 방송 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="broadcast_start",
            limit=limit, 
            offset=offset
        )
        
        # 방송 알림 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_broadcast_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 방송 알림 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 방송 알림 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="방송 알림 조회 중 오류가 발생했습니다.")


@router.get("/notifications/all", response_model=HomeshoppingNotificationListResponse)
async def get_all_notifications_api(
        limit: int = Query(20, ge=1, le=100, description="조회할 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 모든 알림 통합 조회 (주문 + 방송)
    """
    logger.info(f"홈쇼핑 모든 알림 통합 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            limit=limit, 
            offset=offset
        )
        
        # 모든 알림 통합 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_all_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 모든 알림 통합 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 모든 알림 통합 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="모든 알림 통합 조회 중 오류가 발생했습니다.")


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read_api(
        notification_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 알림 읽음 처리
    """
    logger.info(f"홈쇼핑 알림 읽음 처리 요청: user_id={current_user.user_id}, notification_id={notification_id}")
    
    try:
        success = await mark_notification_as_read(db, current_user.user_id, notification_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        
        # 알림 읽음 처리 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_notification_read", 
                event_data={"notification_id": notification_id}
            )
        
        logger.info(f"홈쇼핑 알림 읽음 처리 완료: notification_id={notification_id}")
        return {"message": "알림이 읽음으로 표시되었습니다."}
        
    except Exception as e:
        logger.error(f"홈쇼핑 알림 읽음 처리 실패: notification_id={notification_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="알림 읽음 처리 중 오류가 발생했습니다.")
