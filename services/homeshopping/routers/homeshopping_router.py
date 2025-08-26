"""
홈쇼핑 API 라우터 (MariaDB)
- 편성표 조회, 상품 검색, 찜 기능, 주문 등 홈쇼핑 관련 기능

계층별 역할:
- 이 파일은 API 라우터 계층을 담당
- HTTP 요청/응답 처리, 파라미터 파싱, 유저 인증/권한 확인
- 비즈니스 로직은 CRUD 함수 호출만 하고 직접 DB 처리하지 않음
- 트랜잭션 관리(commit/rollback)를 담당하여 데이터 일관성 보장
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import date

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
    HomeshoppingNotificationUpdate,
    
    # KOK 상품 기반 홈쇼핑 추천 관련 스키마
    KokHomeshoppingRecommendationRequest,
    KokHomeshoppingRecommendationResponse,
    KokHomeshoppingRecommendationProduct
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
    mark_notification_as_read,
    
    # KOK 상품 기반 홈쇼핑 추천 관련 CRUD
    get_kok_product_name_by_id,
    get_homeshopping_recommendations_by_kok,
    get_homeshopping_recommendations_fallback
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
        live_date: Optional[date] = Query(None, description="조회할 날짜 (YYYY-MM-DD 형식, 미입력시 전체 스케줄)"),
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 편성표 조회 (식품만)
    - live_date가 제공되면 해당 날짜의 스케줄만 조회
    - live_date가 미입력시 전체 스케줄 조회
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 편성표 조회 요청: user_id={user_id}, live_date={live_date}")
    
    schedules = await get_homeshopping_schedule(db, live_date=live_date)
    
    # 편성표 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_schedule_view", 
            event_data={"live_date": live_date.isoformat() if live_date else None}
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
        current_user: UserOut = Depends(get_current_user_optional),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 검색
    """
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 검색 요청: user_id={user_id}, keyword='{keyword}'")
    
    products = await search_homeshopping_products(db, keyword)
    
    # 검색 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search", 
            event_data={"keyword": keyword}
        )
    
    logger.info(f"홈쇼핑 상품 검색 완료: user_id={user_id}, keyword='{keyword}', 결과 수={len(products)}")
    return {
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
    
    try:
        saved_history = await add_homeshopping_search_history(db, current_user.user_id, search_data.keyword)
        await db.commit()
        
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
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 검색 이력 저장 실패: user_id={current_user.user_id}, keyword='{search_data.keyword}', error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 저장 중 오류가 발생했습니다.")


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
    
    try:
        success = await delete_homeshopping_search_history(db, current_user.user_id, delete_data.homeshopping_history_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="삭제할 검색 이력을 찾을 수 없습니다.")
        
        await db.commit()
        
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
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 검색 이력 삭제 실패: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 삭제 중 오류가 발생했습니다.")


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
    
    try:
        liked = await toggle_homeshopping_likes(db, current_user.user_id, like_data.product_id)
        await db.commit()
        
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
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 찜 토글 실패: user_id={current_user.user_id}, product_id={like_data.product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜 토글 중 오류가 발생했습니다.")


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
        
        await db.commit()
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 알림 읽음 처리 실패: notification_id={notification_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="알림 읽음 처리 중 오류가 발생했습니다.")

# ================================
# KOK 상품 기반 홈쇼핑 추천 API
# ================================

@router.get("/kok-product/{product_id}/homeshopping-recommendations", response_model=KokHomeshoppingRecommendationResponse)
async def get_homeshopping_recommendations_by_kok(
    request: Request,
    product_id: int,
    k: int = Query(5, ge=1, le=20, description="추천 상품 개수"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    KOK 상품을 기반으로 유사한 홈쇼핑 상품 추천
    - 마지막 의미 토큰, 핵심 키워드, Tail 키워드 등 다양한 알고리즘 사용
    """
    try:
        current_user = await get_current_user_optional(request)
        user_id = current_user.user_id if current_user else None
        logger.info(f"KOK 기반 홈쇼핑 추천 요청: user_id={user_id}, product_id={product_id}, k={k}")
        
        # 1. KOK 상품명 조회
        kok_product_name = await get_kok_product_name_by_id(db, product_id)
        if not kok_product_name:
            raise HTTPException(status_code=404, detail="KOK 상품을 찾을 수 없습니다.")
        
        # 2. 추천 전략 선택 및 실행
        from services.kok.utils.recommendation_utils import get_recommendation_strategy
        
        strategy_result = get_recommendation_strategy(kok_product_name, k)
        algorithm_info = {
            "algorithm": strategy_result["algorithm"],
            "status": strategy_result["status"],
            "search_terms": strategy_result.get("search_terms", [])
        }
        
        # 3. 홈쇼핑 상품 추천 조회
        recommendations = []
        if strategy_result["status"] == "success" and strategy_result.get("search_terms"):
            recommendations = await get_homeshopping_recommendations_by_kok(
                db, kok_product_name, strategy_result["search_terms"], k
            )
        
        # 4. 추천 결과가 부족한 경우 폴백 전략 사용
        if len(recommendations) < k:
            fallback_recommendations = await get_homeshopping_recommendations_fallback(
                db, kok_product_name, k - len(recommendations)
            )
            recommendations.extend(fallback_recommendations)
            algorithm_info["fallback_used"] = True
            algorithm_info["fallback_count"] = len(fallback_recommendations)
        
        # 5. 응답 데이터 구성
        response_products = []
        for rec in recommendations:
            response_products.append(KokHomeshoppingRecommendationProduct(
                product_id=rec["product_id"],
                product_name=rec["product_name"],
                store_name=rec["store_name"],
                sale_price=rec["sale_price"],
                dc_price=rec["dc_price"],
                dc_rate=rec["dc_rate"],
                thumb_img_url=rec["thumb_img_url"],
                live_date=rec["live_date"],
                live_start_time=rec["live_start_time"],
                live_end_time=rec["live_end_time"],
                similarity_score=None  # 향후 유사도 점수 계산 로직 추가 가능
            ))
        
        # 6. 인증된 사용자의 경우에만 로그 기록
        if current_user and background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_homeshopping_recommendation", 
                event_data={
                    "kok_product_id": product_id,
                    "kok_product_name": kok_product_name,
                    "recommendation_count": len(response_products),
                    "algorithm": strategy_result["algorithm"],
                    "k": k
                }
            )
        
        logger.info(f"KOK 기반 홈쇼핑 추천 완료: user_id={user_id}, product_id={product_id}, 결과 수={len(response_products)}")
        
        return KokHomeshoppingRecommendationResponse(
            kok_product_id=product_id,
            kok_product_name=kok_product_name,
            recommendations=response_products,
            total_count=len(response_products),
            algorithm_info=algorithm_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KOK 기반 홈쇼핑 추천 API 오류: product_id={product_id}, user_id={user_id}, error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"홈쇼핑 추천 중 오류가 발생했습니다: {str(e)}"
        )
