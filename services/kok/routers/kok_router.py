"""
콕 쇼핑몰 API 라우터 (MariaDB)
- 메인화면 상품정보, 상품 상세, 검색, 찜, 장바구니 기능

계층별 역할:
- 이 파일은 API 라우터 계층을 담당
- HTTP 요청/응답 처리, 파라미터 파싱, 유저 인증/권한 확인
- 비즈니스 로직은 CRUD 함수 호출만 하고 직접 DB 처리하지 않음
- 트랜잭션 관리(commit/rollback)를 담당하여 데이터 일관성 보장
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from common.dependencies import (
    get_current_user, get_current_user_optional
)
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.kok.models.kok_model import KokCart
from services.user.schemas.user_schema import UserOut
from services.homeshopping.schemas.homeshopping_schema import (
    KokHomeshoppingRecommendationProduct, 
    KokHomeshoppingRecommendationResponse
)
from services.kok.schemas.kok_schema import (
    # 제품 관련 스키마
    KokProductInfoResponse,
    KokProductTabsResponse,

    # 리뷰 관련 스키마      
    KokReviewResponse,

    # 상품 상세정보 스키마
    KokProductDetailsResponse,

    # 메인화면 상품 리스트 스키마
    KokDiscountedProductsResponse,
    KokTopSellingProductsResponse,
    KokStoreBestProductsResponse,

    # 찜 관련 스키마
    KokLikesToggleRequest,
    KokLikesToggleResponse,
    KokLikedProductsResponse,

    # 장바구니 관련 스키마
    KokCartItemsResponse,
    KokCartAddRequest,
    KokCartAddResponse,
    KokCartUpdateRequest,
    KokCartUpdateResponse,
    KokCartDeleteResponse,
    KokCartRecipeRecommendResponse,

    # 검색 관련 스키마
    KokSearchResponse,
    KokSearchHistoryResponse,
    KokSearchHistoryCreate,
    KokSearchHistoryDeleteResponse
)
from services.homeshopping.crud.homeshopping_crud import (
    get_kok_product_name_by_id, 
    get_homeshopping_recommendations_by_kok, 
    get_homeshopping_recommendations_fallback
)
from services.kok.utils.kok_homeshopping import get_recommendation_strategy

from services.kok.crud.kok_crud import (
    # 제품 관련 CRUD
    get_kok_product_info,
    get_kok_product_tabs,
    get_kok_product_seller_details,

    # 리뷰 관련 CRUD
    get_kok_review_data,

    # 메인화면 상품 리스트 CRUD
    get_kok_discounted_products,
    get_kok_top_selling_products,
    get_kok_store_best_items,

    # 찜 관련 CRUD
    toggle_kok_likes,
    get_kok_liked_products,

    # 장바구니 관련 CRUD
    get_kok_cart_items,
    add_kok_cart,
    update_kok_cart_quantity,
    delete_kok_cart_item,

    # 검색 관련 CRUD
    search_kok_products,
    get_kok_search_history,
    add_kok_search_history,
    delete_kok_search_history,

    # 장바구니 관련 CRUD
    get_ingredients_from_cart_product_ids
)
from services.kok.utils.kok_homeshopping import (
    get_recommendation_strategy
)
from services.kok.utils.cache_utils import cache_manager
from services.recipe.crud.recipe_crud import recommend_by_recipe_pgvector

logger = get_logger("kok_router")
router = APIRouter(prefix="/api/kok", tags=["Kok"])


# ================================
# 메인화면 상품정보
# ================================

@router.get("/discounted", response_model=KokDiscountedProductsResponse)
async def get_discounted_products(
        request: Request,
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        use_cache: bool = Query(True, description="캐시 사용 여부"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회 (성능 최적화 적용)
    - N+1 쿼리 문제 해결
    - Redis 캐싱 적용 (5분 TTL)
    - 데이터베이스 인덱스 최적화
    """
    import time
    start_time = time.time()
    
    logger.debug(f"할인 상품 조회 시작: page={page}, size={size}, use_cache={use_cache}")
    
    # 공통 디버깅 함수 사용
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning("인증되지 않은 사용자가 할인 상품 조회 요청")
    
    logger.info(f"할인 상품 조회 요청: user_id={user_id}, page={page}, size={size}, use_cache={use_cache}")
    
    try:
        products = await get_kok_discounted_products(db, page=page, size=size, use_cache=use_cache)
        logger.debug(f"할인 상품 조회 성공: 결과 수={len(products)}")
    except Exception as e:
        logger.error(f"할인 상품 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="할인 상품 조회 중 오류가 발생했습니다.")
    
    # 성능 측정
    execution_time = (time.time() - start_time) * 1000  # ms 단위
    logger.info(f"할인 상품 조회 성능: user_id={user_id}, 실행시간={execution_time:.2f}ms, 결과 수={len(products)}")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_discounted_products_view", 
            event_data={
                "product_count": len(products),
                "execution_time_ms": round(execution_time, 2),
                "use_cache": use_cache
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return KokDiscountedProductsResponse(products=products)


@router.get("/top-selling", response_model=KokTopSellingProductsResponse)
async def get_top_selling_products(
        request: Request,
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        sort_by: str = Query("review_count", description="정렬 기준 (review_count: 리뷰 개수 순, rating: 별점 평균 순)"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    판매율 높은 상품 리스트 조회
    - sort_by: review_count (리뷰 개수 순) 또는 rating (별점 평균 순)
    """
    logger.debug(f"인기 상품 조회 시작: page={page}, size={size}, sort_by={sort_by}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning("인증되지 않은 사용자가 인기 상품 조회 요청")
    
    logger.info(f"인기 상품 조회 요청: user_id={user_id}, page={page}, size={size}, sort_by={sort_by}")
    
    try:
        products = await get_kok_top_selling_products(db, page=page, size=size, sort_by=sort_by)
        logger.debug(f"인기 상품 조회 성공: 결과 수={len(products)}")
    except Exception as e:
        logger.error(f"인기 상품 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="인기 상품 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_top_selling_products_view", 
            event_data={"product_count": len(products), "sort_by": sort_by},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"인기 상품 조회 완료: user_id={user_id}, 결과 수={len(products)}, sort_by={sort_by}")
    return {"products": products}
    

@router.get("/store-best-items", response_model=KokStoreBestProductsResponse)
async def get_store_best_items(
        request: Request,
        sort_by: str = Query("review_count", description="정렬 기준 (review_count: 리뷰 개수 순, rating: 별점 평균 순)"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    구매한 스토어의 베스트 상품 리스트 조회
    - sort_by: review_count (리뷰 개수 순) 또는 rating (별점 평균 순)
    """
    logger.debug(f"스토어 베스트 상품 조회 시작: sort_by={sort_by}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning("인증되지 않은 사용자가 스토어 베스트 상품 조회 요청")
    
    logger.info(f"스토어 베스트 상품 조회 요청: user_id={user_id}, sort_by={sort_by}")
    
    try:
        products = await get_kok_store_best_items(db, user_id, sort_by=sort_by)
        logger.debug(f"스토어 베스트 상품 조회 성공: 결과 수={len(products)}")
    except Exception as e:
        logger.error(f"스토어 베스트 상품 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="스토어 베스트 상품 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_store_best_items_view", 
            event_data={"product_count": len(products), "sort_by": sort_by},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"스토어 베스트 상품 조회 완료: user_id={user_id}, 결과 수={len(products)}, sort_by={sort_by}")
    return {"products": products}


# ================================
# 상품 상세 설명
# ================================

@router.get("/product/{kok_product_id}/info", response_model=KokProductInfoResponse)
async def get_product_info(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 기본 정보 조회
    """
    logger.debug(f"상품 기본 정보 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 기본 정보 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 기본 정보 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        product = await get_kok_product_info(db, kok_product_id, user_id)
        if not product:
            logger.warning(f"상품을 찾을 수 없음: kok_product_id={kok_product_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 기본 정보 조회 성공: kok_product_id={kok_product_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 기본 정보 조회 실패: kok_product_id={kok_product_id}, user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 기본 정보 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_info_view", 
            event_data={"kok_product_id": kok_product_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 기본 정보 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return product


@router.get("/product/{kok_product_id}/tabs", response_model=KokProductTabsResponse)
async def get_product_tabs(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 설명 탭 정보 조회
    """
    logger.debug(f"상품 탭 정보 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 탭 정보 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 탭 정보 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        images_response = await get_kok_product_tabs(db, kok_product_id)
        if images_response is None:
            logger.warning(f"상품 탭 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 탭 정보 조회 성공: kok_product_id={kok_product_id}, 탭 수={len(images_response.images)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 탭 정보 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 탭 정보 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_tabs_view", 
            event_data={"kok_product_id": kok_product_id, "tab_count": len(images_response.images)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 탭 정보 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return images_response


@router.get("/product/{kok_product_id}/reviews", response_model=KokReviewResponse)
async def get_product_reviews(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 리뷰 탭 정보 조회
    - KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보
    - KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록
    """
    logger.debug(f"상품 리뷰 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 리뷰 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 리뷰 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        review_data = await get_kok_review_data(db, kok_product_id)
        if review_data is None:
            logger.warning(f"상품 리뷰 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 리뷰 조회 성공: kok_product_id={kok_product_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 리뷰 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 리뷰 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_reviews_view", 
            event_data={"kok_product_id": kok_product_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 리뷰 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return review_data


# ================================
# 제품 상세 정보
# ================================

@router.get("/product/{kok_product_id}/seller-details", response_model=KokProductDetailsResponse)
async def get_product_details(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 판매자 정보 및 상세정보 조회
    """
    logger.debug(f"상품 상세 정보 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 상세 정보 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 상세 정보 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        product_details = await get_kok_product_seller_details(db, kok_product_id)
        if not product_details:
            logger.warning(f"상품 상세 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 상세 정보 조회 성공: kok_product_id={kok_product_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 상세 정보 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 상세 정보 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_details_view", 
            event_data={"kok_product_id": kok_product_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 상세 정보 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return product_details


# ================================
# 검색 관련 API
# ================================

@router.get("/search", response_model=KokSearchResponse)
async def search_products(
    request: Request,
    keyword: str = Query(..., description="검색 키워드"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    키워드 기반으로 콕 쇼핑몰 내에 있는 상품을 검색
    """
    logger.debug(f"상품 검색 시작: keyword='{keyword}', page={page}, size={size}")
    
    try:
        current_user = await get_current_user_optional(request)
        user_id = current_user.user_id if current_user else None
        
        if not current_user:
            logger.warning(f"인증되지 않은 사용자가 상품 검색 요청: keyword='{keyword}'")
        
        logger.info(f"상품 검색 요청: user_id={user_id}, keyword='{keyword}', page={page}, size={size}")
        
        products, total = await search_kok_products(db, keyword, page, size)
        logger.debug(f"상품 검색 성공: keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
        logger.info(f"상품 검색 완료: user_id={user_id}, keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
        
        # 인증된 사용자의 경우에만 로그 기록과 검색 기록 저장
        if current_user and background_tasks:
            # 검색 로그 기록
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_product_search", 
                event_data={"keyword": keyword, "result_count": len(products)},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
            
            # 검색 기록 저장
            background_tasks.add_task(
                add_kok_search_history,
                db=db,
                user_id=current_user.user_id,
                keyword=keyword
            )
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "products": products
        }
        
    except Exception as e:
        logger.error(f"상품 검색 API 오류: keyword='{keyword}', user_id={user_id}, error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"상품 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/search/history", response_model=KokSearchHistoryResponse)
async def get_search_history(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="조회할 이력 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 조회
    """
    logger.debug(f"검색 이력 조회 시작: user_id={current_user.user_id}, limit={limit}")
    
    try:
        history = await get_kok_search_history(db, current_user.user_id, limit)
        logger.debug(f"검색 이력 조회 성공: user_id={current_user.user_id}, 결과 수={len(history)}")
    except Exception as e:
        logger.error(f"검색 이력 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 조회 중 오류가 발생했습니다.")
    
    # 검색 이력 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_search_history_view", 
            event_data={"history_count": len(history)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"history": history}


@router.post("/search/history", response_model=dict)
async def add_search_history(
    request: Request,
    search_data: KokSearchHistoryCreate,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 저장
    """
    logger.debug(f"검색 이력 추가 시작: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    logger.info(f"검색 이력 추가 요청: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    
    try:
        saved_history = await add_kok_search_history(db, current_user.user_id, search_data.keyword)
        await db.commit()
        logger.debug(f"검색 이력 추가 성공: user_id={current_user.user_id}, history_id={saved_history['kok_history_id']}")
        logger.info(f"검색 이력 추가 완료: user_id={current_user.user_id}, history_id={saved_history['kok_history_id']}")
        
        # 검색 이력 저장 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_search_history_save", 
                event_data={"keyword": search_data.keyword},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return {
            "message": "검색 이력이 저장되었습니다.",
            "saved": saved_history
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"검색 이력 추가 실패: user_id={current_user.user_id}, keyword='{search_data.keyword}', error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 저장 중 오류가 발생했습니다.")


@router.delete("/search/history/{history_id}", response_model=KokSearchHistoryDeleteResponse)
async def delete_search_history(
    request: Request,
    history_id: int,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 삭제
    """
    logger.debug(f"검색 이력 삭제 시작: user_id={current_user.user_id}, history_id={history_id}")
    logger.info(f"검색 이력 삭제 요청: user_id={current_user.user_id}, history_id={history_id}")
    
    try:
        deleted = await delete_kok_search_history(db, current_user.user_id, history_id)
        
        if deleted:
            await db.commit()
            logger.debug(f"검색 이력 삭제 성공: user_id={current_user.user_id}, history_id={history_id}")
            logger.info(f"검색 이력 삭제 완료: user_id={current_user.user_id}, history_id={history_id}")
            
            # 검색 이력 삭제 로그 기록
            if background_tasks:
                http_info = extract_http_info(request, response_code=200)
                background_tasks.add_task(
                    send_user_log, 
                    user_id=current_user.user_id, 
                    event_type="kok_search_history_delete", 
                    event_data={"history_id": history_id},
                    **http_info  # HTTP 정보를 키워드 인자로 전달
                )
            
            return {"message": f"검색 이력 ID {history_id}가 삭제되었습니다."}
        else:
            logger.warning(f"검색 이력을 찾을 수 없음: user_id={current_user.user_id}, history_id={history_id}")
            raise HTTPException(status_code=404, detail="해당 검색 이력을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"검색 이력 삭제 실패: user_id={current_user.user_id}, history_id={history_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 삭제 중 오류가 발생했습니다.")


# ================================
# 찜 관련 API
# ================================

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


# ================================
# 장바구니 관련 API
# ================================

@router.post("/carts", response_model=KokCartAddResponse, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    request: Request,
    cart_data: KokCartAddRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에 상품 추가
    """
    logger.debug(f"장바구니 추가 시작: user_id={current_user.user_id}, kok_product_id={cart_data.kok_product_id}, kok_quantity={cart_data.kok_quantity}, recipe_id={cart_data.recipe_id}")
    logger.info(f"장바구니 추가 요청: user_id={current_user.user_id}, kok_product_id={cart_data.kok_product_id}, kok_quantity={cart_data.kok_quantity}, recipe_id={cart_data.recipe_id}")
    
    try:
        result = await add_kok_cart(
            db,
            current_user.user_id,
            cart_data.kok_product_id,
            cart_data.kok_quantity,
            cart_data.recipe_id,
        )
        await db.commit()
        
        # commit 후에 새로 생성된 cart_id를 조회
        stmt = select(KokCart).where(
            KokCart.user_id == current_user.user_id,
            KokCart.kok_product_id == cart_data.kok_product_id
        ).order_by(KokCart.kok_cart_id.desc()).limit(1)
        
        cart_result = await db.execute(stmt)
        new_cart = cart_result.scalar_one()
        actual_cart_id = new_cart.kok_cart_id if new_cart else 0
        logger.debug(f"장바구니 추가 성공: user_id={current_user.user_id}, kok_cart_id={actual_cart_id}")
        logger.info(f"장바구니 추가 완료: user_id={current_user.user_id}, kok_cart_id={actual_cart_id}, message={result['message']}")
        
        # 장바구니 추가 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_cart_add", 
                event_data={
                    "kok_product_id": cart_data.kok_product_id,
                    "kok_quantity": cart_data.kok_quantity,
                    "kok_cart_id": actual_cart_id,
                    "recipe_id": cart_data.recipe_id
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return KokCartAddResponse(
            kok_cart_id=actual_cart_id,
            message=result["message"]
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"장바구니 추가 실패: user_id={current_user.user_id}, kok_product_id={cart_data.kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 추가 중 오류가 발생했습니다.")
    

@router.get("/carts", response_model=KokCartItemsResponse)
async def get_cart_items(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="조회할 장바구니 상품 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 목록 조회
    """
    logger.debug(f"장바구니 상품 목록 조회 시작: user_id={current_user.user_id}, limit={limit}")
    
    try:
        cart_items = await get_kok_cart_items(db, current_user.user_id, limit)
        logger.debug(f"장바구니 상품 목록 조회 성공: user_id={current_user.user_id}, 결과 수={len(cart_items)}")
    except Exception as e:
        logger.error(f"장바구니 상품 목록 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 상품 목록 조회 중 오류가 발생했습니다.")
    
    # 장바구니 상품 목록 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_cart_items_view", 
            event_data={
                "limit": limit,
                "item_count": len(cart_items)
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"cart_items": cart_items}


@router.patch("/carts/{kok_cart_id}", response_model=KokCartUpdateResponse)
async def update_cart_quantity(
    request: Request,
    kok_cart_id: int,
    update_data: KokCartUpdateRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니 상품 수량 변경
    """
    logger.debug(f"장바구니 수량 변경 시작: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}, quantity={update_data.kok_quantity}")
    
    try:
        result = await update_kok_cart_quantity(db, current_user.user_id, kok_cart_id, update_data.kok_quantity)
        await db.commit()
        logger.debug(f"장바구니 수량 변경 성공: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
        
        # 장바구니 수량 변경 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_cart_update", 
                event_data={
                    "kok_cart_id": kok_cart_id,
                    "quantity": update_data.kok_quantity
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return KokCartUpdateResponse(
            kok_cart_id=result["kok_cart_id"],
            kok_quantity=result["kok_quantity"],
            message=result["message"]
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"장바구니 수량 변경 실패: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 수량 변경 중 오류가 발생했습니다.")


@router.delete("/carts/{kok_cart_id}", response_model=KokCartDeleteResponse)
async def delete_cart_item(
    request: Request,
    kok_cart_id: int,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에서 상품 삭제
    """
    logger.debug(f"장바구니 삭제 시작: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
    
    try:
        deleted = await delete_kok_cart_item(db, current_user.user_id, kok_cart_id)
        
        if deleted:
            await db.commit()
            logger.debug(f"장바구니 삭제 성공: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
            
            # 장바구니 삭제 로그 기록
            if background_tasks:
                http_info = extract_http_info(request, response_code=200)
                background_tasks.add_task(
                    send_user_log, 
                    user_id=current_user.user_id, 
                    event_type="kok_cart_delete", 
                    event_data={"kok_cart_id": kok_cart_id},
                    **http_info  # HTTP 정보를 키워드 인자로 전달
                )
            
            return KokCartDeleteResponse(message="장바구니에서 상품이 삭제되었습니다.")
        else:
            logger.warning(f"장바구니 항목을 찾을 수 없음: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}")
            raise HTTPException(status_code=404, detail="장바구니 항목을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"장바구니 삭제 실패: user_id={current_user.user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="장바구니 삭제 중 오류가 발생했습니다.")


@router.get("/carts/recipe-recommend", response_model=KokCartRecipeRecommendResponse)
async def recommend_recipes_from_cart_items(
    request: Request,
    product_ids: str = Query(..., description="상품 ID 목록 (쉼표로 구분) - KOK 또는 홈쇼핑 상품 ID 혼용 가능"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(10, ge=1, le=100, description="페이지당 레시피 수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    장바구니에서 선택한 상품들의 product_ids를 받아서 키워드 추출 후 레시피 추천
    - KOK 상품: KOK_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 홈쇼핑 상품: HOMESHOPPING_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 해당 상품들의 product_name에서 키워드 추출
    - recipe 폴더 내에서 식재료명 기반 레시피 추천 로직을 사용
    """
    logger.debug(f"레시피 추천 시작: user_id={current_user.user_id}, product_ids={product_ids}, page={page}, size={size}")
    
    try:
        # 통합 상품 ID 파싱 (KOK 또는 홈쇼핑 상품 ID 혼용 가능)
        all_product_ids = [int(pid.strip()) for pid in product_ids.split(",") if pid.strip().isdigit()]
        
        if not all_product_ids:
            logger.warning(f"유효한 상품 ID가 없음: product_ids={product_ids}")
            raise HTTPException(status_code=400, detail="유효한 상품 ID가 없습니다.")
        
        logger.info(f"레시피 추천 요청: user_id={current_user.user_id}, product_ids={all_product_ids}, page={page}, size={size}")
        
        # KOK와 홈쇼핑 상품에서 재료명 추출
        logger.debug("상품에서 재료명 추출 시작")
        ingredients = await get_ingredients_from_cart_product_ids(
            db, [], [], all_product_ids
        )
        
        if not ingredients:
            logger.warning(f"추출된 재료가 없음: user_id={current_user.user_id}")
            return KokCartRecipeRecommendResponse(
                recipes=[],
                total_count=0,
                page=page,
                size=size,
                total_pages=0,
                keyword_extraction=[]
            )
        
        logger.info(f"재료 추출 성공: {ingredients}")
        
        # 추출된 재료를 기반으로 레시피 추천 (pgvector 기반 ingredient 방식)
        # 쉼표로 구분된 재료명을 하나의 문자열로 결합
        ingredients_query = ",".join(ingredients)
        logger.debug(f"레시피 추천 쿼리 생성: {ingredients_query}")
        
        # recommend_by_recipe_pgvector 함수 호출 (method="ingredient")
        # ingredient 모드에서는 vector_searcher가 필요하지 않지만 함수 시그니처상 필수
        # None을 전달하여 실제 사용하지 않음을 표시
        logger.debug("레시피 추천 실행 시작")
        recipes_df = await recommend_by_recipe_pgvector(
            mariadb=db,
            postgres=db,  # MariaDB를 postgres로도 사용 (ingredient 모드에서는 pgvector 사용 안함)
            query=ingredients_query,
            method="ingredient",
            page=page,
            size=size,
            include_materials=True,
            vector_searcher=None  # ingredient 모드에서는 사용하지 않음
        )
        logger.debug(f"레시피 추천 결과: DataFrame 크기={len(recipes_df)}")
        
        # DataFrame을 응답 형식에 맞게 변환
        logger.debug("DataFrame을 응답 형식으로 변환 시작")
        recipes = []
        if not recipes_df.empty:
            logger.debug(f"레시피 데이터 변환: {len(recipes_df)}개 레시피 처리")
            for _, row in recipes_df.iterrows():
                recipe_dict = {
                    "recipe_id": int(row["RECIPE_ID"]),
                    "recipe_title": str(row.get("RECIPE_TITLE", "")) if row.get("RECIPE_TITLE") else None,
                    "cooking_name": str(row.get("COOKING_NAME", "")) if row.get("COOKING_NAME") else None,
                    "description": str(row.get("COOKING_INTRODUCTION", "")) if row.get("COOKING_INTRODUCTION") else None,
                    "scrap_count": int(row["SCRAP_COUNT"]) if row["SCRAP_COUNT"] is not None and not (isinstance(row["SCRAP_COUNT"], float) and pd.isna(row["SCRAP_COUNT"])) else 0,
                    "recipe_url": f"https://www.10000recipe.com/recipe/{int(row['RECIPE_ID'])}",
                    "number_of_serving": str(row.get("NUMBER_OF_SERVING", "")) if row.get("NUMBER_OF_SERVING") else None,
                    "ingredients": []
                }
                
                # 재료 정보가 있으면 ingredients 배열에 재료명만 추가
                if "MATERIALS" in row and row["MATERIALS"] is not None:
                    try:
                        # pandas의 NaN 값 체크를 안전하게 수행
                        if not (isinstance(row["MATERIALS"], float) and pd.isna(row["MATERIALS"])):
                            for material in row["MATERIALS"]:
                                material_name = material.get("MATERIAL_NAME", "")
                                if material_name:
                                    recipe_dict["ingredients"].append(material_name)
                    except:
                        # 에러가 발생하면 재료 정보를 추가하지 않음
                        pass
                
                recipes.append(recipe_dict)
        else:
            logger.debug("추천된 레시피가 없음")
        
        total_count = len(recipes)
        total_pages = (total_count + size - 1) // size
        logger.info(f"레시피 추천 완료: {len(recipes)}개 레시피, 총 {total_count}개")
        
        # 레시피 추천 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_cart_recipe_recommend", 
                event_data={
                    "product_ids": all_product_ids,
                    "extracted_ingredients": ingredients,
                    "recommended_recipes_count": len(recipes),
                    "page": page,
                    "size": size
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return KokCartRecipeRecommendResponse(
            recipes=recipes,
            total_count=total_count,
            page=page,
            size=size,
            total_pages=total_pages,
            keyword_extraction=ingredients
        )
    except ValueError as e:
        logger.warning(f"레시피 추천 검증 오류: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"레시피 추천 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 추천 중 오류가 발생했습니다.")
        

# ================================
# 홈쇼핑 추천 API (KOK utils 사용)
# ================================

@router.get("/product/homeshopping-recommend")
async def get_homeshopping_recommend(
    request: Request,
    k: int = Query(5, ge=1, le=20, description="추천 상품 개수"),
    background_tasks: BackgroundTasks = None,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    현재 사용자의 KOK 찜/장바구니 상품을 기반으로 유사한 홈쇼핑 상품 추천
    - 사용자의 찜 목록과 장바구니 목록에서 kok_product_id 자동 수집
    - KOK utils의 추천 알고리즘 사용
    """
    logger.debug(f"홈쇼핑 추천 시작: user_id={current_user.user_id}, k={k}")
    
    try:
        user_id = current_user.user_id
        logger.info(f"홈쇼핑 추천 요청: user_id={user_id}, k={k}")
        
        # 1. 현재 사용자의 KOK 찜 목록과 장바구니 목록에서 kok_product_id 수집
        logger.debug("사용자의 찜 목록과 장바구니 목록에서 상품 ID 수집 시작")
        # 찜한 상품들의 kok_product_id 수집
        liked_products = await get_kok_liked_products(db, user_id, limit=100)
        liked_product_ids = [product["kok_product_id"] for product in liked_products]
        
        # 장바구니 상품들의 kok_product_id 수집
        cart_items = await get_kok_cart_items(db, user_id, limit=100)
        cart_product_ids = [item["kok_product_id"] for item in cart_items]
        
        # 중복 제거하여 고유한 kok_product_id 목록 생성
        all_product_ids = list(set(liked_product_ids + cart_product_ids))
        
        if not all_product_ids:
            logger.warning(f"찜하거나 장바구니에 담긴 상품이 없음: user_id={user_id}")
            raise HTTPException(status_code=400, detail="찜하거나 장바구니에 담긴 상품이 없습니다.")
        
        logger.info(f"수집된 KOK 상품 ID: 찜={len(liked_product_ids)}개, 장바구니={len(cart_product_ids)}개, 총={len(all_product_ids)}개")
        
        # 2. 각 KOK 상품명 조회 및 추천 키워드 수집        
        logger.debug("각 KOK 상품명 조회 및 추천 키워드 수집 시작")
        all_search_terms = set()
        kok_product_names = []
        
        for product_id in all_product_ids:
            try:
                kok_product_name = await get_kok_product_name_by_id(db, product_id)
                if kok_product_name:
                    kok_product_names.append(kok_product_name)
                    # 각 상품명에서 추천 키워드 추출
                    try:
                        recommendation_result = get_recommendation_strategy(kok_product_name, 5) # 각 상품당 최대 5개
                        if recommendation_result and recommendation_result.get("status") == "success":
                            search_terms = recommendation_result.get("search_terms", [])
                            all_search_terms.update(search_terms)
                            logger.info(f"상품 '{kok_product_name}'에서 추출된 키워드: {search_terms}")
                        else:
                            logger.warning(f"상품 '{kok_product_name}'에서 키워드 추출 실패: {recommendation_result}")
                    except Exception as e:
                        logger.error(f"상품 '{kok_product_name}' 키워드 추출 중 오류: {str(e)}")
                        continue
            except Exception as e:
                logger.warning(f"상품 ID {product_id} 조회 실패: {str(e)}")
                continue
        
        if not all_search_terms:
            logger.warning(f"추천 키워드를 추출할 수 없음: user_id={user_id}")
            raise HTTPException(status_code=400, detail="추천 키워드를 추출할 수 없습니다.")
        
        logger.info(f"추출된 추천 키워드: {list(all_search_terms)}")
        
        # 3. 각 KOK 상품별로 홈쇼핑 상품 추천 조회 (각각 최대 5개씩)        
        logger.debug("각 KOK 상품별로 홈쇼핑 상품 추천 조회 시작")
        all_recommendations = []
        product_recommendations = {}  # 각 상품별 추천 결과를 저장
        
        # 각 KOK 상품별로 추천 조회
        for product_id, product_name in zip(all_product_ids, kok_product_names):
            if not product_name:
                continue
                
            try:
                # 각 상품명에서 추천 키워드 추출
                recommendation_result = get_recommendation_strategy(product_name, 5)  # 각 상품당 최대 5개
                if not recommendation_result or recommendation_result.get("status") != "success":
                    logger.warning(f"상품 '{product_name}'에서 키워드 추출 실패: {recommendation_result}")
                    continue
                search_terms = recommendation_result.get("search_terms", [])
                if not search_terms:
                    logger.warning(f"상품 '{product_name}'에서 추출된 키워드가 없음")
                    continue
                logger.info(f"상품 '{product_name}'에서 추출된 키워드: {search_terms}")
                
                # 검색 조건을 더 유연하게 구성
                search_conditions = []
                for term in search_terms:
                    # 정확한 키워드 매칭
                    search_conditions.append(f"c.PRODUCT_NAME LIKE '%{term}%'")
                    # 브랜드명 매칭 (대괄호 안의 내용)
                    if '[' in product_name and ']' in product_name:
                        brand = product_name.split('[')[1].split(']')[0]
                        search_conditions.append(f"c.PRODUCT_NAME LIKE '%{brand}%'")
                
                # 해당 상품에 대한 추천 조회
                logger.debug(f"상품 '{product_name}'에 대한 홈쇼핑 추천 조회 시작")
                product_recs = await get_homeshopping_recommendations_by_kok(
                    db, product_name, search_conditions, 5
                )
                
                if not product_recs:
                    # 폴백: 상품명에서 주요 키워드만 추출하여 검색
                    logger.debug(f"상품 '{product_name}' 추천 실패, 폴백 시스템 사용")
                    fallback_keywords = [term for term in search_terms if len(term) > 1]
                    if fallback_keywords:
                        fallback_recs = await get_homeshopping_recommendations_fallback(
                            db, fallback_keywords[0], 5
                        )
                        if fallback_recs:
                            product_recs = fallback_recs
                            logger.debug(f"폴백 시스템으로 추천 성공: {len(product_recs)}개")
                
                # 결과 저장
                product_recommendations[product_name] = product_recs
                all_recommendations.extend(product_recs)
                
                logger.info(f"상품 '{product_name}' 추천 완료: {len(product_recs)}개")
                
            except Exception as e:
                logger.error(f"상품 '{product_name}' 추천 실패: {e}")
                product_recommendations[product_name] = []
                continue
        
        # 전체 추천 결과에서 중복 제거 (product_id 기준)
        logger.debug("전체 추천 결과에서 중복 제거 시작")
        seen_product_ids = set()
        final_recommendations = []
        for rec in all_recommendations:
            if rec["product_id"] not in seen_product_ids:
                final_recommendations.append(rec)
                seen_product_ids.add(rec["product_id"])
        
        logger.info(f"전체 추천 결과: {len(final_recommendations)}개 (중복 제거 후)")
        
        algorithm_info = {
            "algorithm": "multi_product_keyword_based",
            "status": "success",
            "search_terms": ", ".join(all_search_terms),
            "source_products_count": str(len(all_product_ids)),
            "liked_products_count": str(len(liked_product_ids)),
            "cart_products_count": str(len(cart_product_ids)),
            "total_recommendations": str(len(final_recommendations)),
            "product_recommendations_count": str(len(product_recommendations))
        }
        
        # 5. 응답 데이터 구성
        response_products = []
        for rec in final_recommendations:
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
        
        # 각 상품별 추천 결과를 스키마 형태로 변환
        product_recommendations_response = {}
        for product_name, recs in product_recommendations.items():
            product_recommendations_response[product_name] = []
            for rec in recs:
                product_recommendations_response[product_name].append(KokHomeshoppingRecommendationProduct(
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
                    similarity_score=None
                ))
        
        # 6. 사용자 활동 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_homeshopping_recommendation", 
                event_data={
                    "source_products_count": len(all_product_ids),
                    "liked_products_count": len(liked_product_ids),
                    "cart_products_count": len(cart_product_ids),
                    "recommendation_count": len(response_products),
                    "algorithm": "multi_product_keyword_based",
                    "k": k
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 추천 완료: user_id={user_id}, 소스 상품={len(all_product_ids)}개, 결과 수={len(response_products)}개")
        
        return KokHomeshoppingRecommendationResponse(
            kok_product_id=None,  # 단일 상품이 아닌 다중 상품 기반
            kok_product_name="사용자 맞춤 추천",  # 다중 상품 기반임을 표시
            recommendations=response_products,
            total_count=len(response_products),
            algorithm_info=algorithm_info,
            product_recommendations=product_recommendations_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"홈쇼핑 추천 API 오류: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"홈쇼핑 추천 중 오류가 발생했습니다: {str(e)}"
        )


# ================================
# 캐시 관리 API
# ================================

@router.post("/cache/invalidate/discounted")
async def invalidate_discounted_cache():
    """
    할인 상품 캐시 무효화
    """
    logger.debug("할인 상품 캐시 무효화 시작")
    
    try:
        deleted_count = cache_manager.invalidate_discounted_products()
        logger.debug(f"할인 상품 캐시 무효화 성공: 삭제된 키 수={deleted_count}")
        logger.info(f"할인 상품 캐시 무효화 완료: 삭제된 키 수={deleted_count}")
        return {"message": f"할인 상품 캐시가 무효화되었습니다. 삭제된 키 수: {deleted_count}"}
    except Exception as e:
        logger.error(f"할인 상품 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")

@router.post("/cache/invalidate/top-selling")
async def invalidate_top_selling_cache():
    """
    인기 상품 캐시 무효화
    """
    logger.debug("인기 상품 캐시 무효화 시작")
    
    try:
        deleted_count = cache_manager.invalidate_top_selling_products()
        logger.debug(f"인기 상품 캐시 무효화 성공: 삭제된 키 수={deleted_count}")
        logger.info(f"인기 상품 캐시 무효화 완료: 삭제된 키 수={deleted_count}")
        return {"message": f"인기 상품 캐시가 무효화되었습니다. 삭제된 키 수: {deleted_count}"}
    except Exception as e:
        logger.error(f"인기 상품 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")

@router.post("/cache/invalidate/store-best")
async def invalidate_store_best_cache():
    """
    스토어 베스트 상품 캐시 무효화
    """
    logger.debug("스토어 베스트 상품 캐시 무효화 시작")
    
    try:
        deleted_count = cache_manager.invalidate_store_best_items()
        logger.debug(f"스토어 베스트 상품 캐시 무효화 성공: 삭제된 키 수={deleted_count}")
        logger.info(f"스토어 베스트 상품 캐시 무효화 완료: 삭제된 키 수={deleted_count}")
        return {"message": f"스토어 베스트 상품 캐시가 무효화되었습니다. 삭제된 키 수: {deleted_count}"}
    except Exception as e:
        logger.error(f"스토어 베스트 상품 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")

@router.post("/cache/invalidate/all")
async def invalidate_all_cache():
    """
    모든 KOK 관련 캐시 무효화
    """
    logger.debug("모든 KOK 관련 캐시 무효화 시작")
    
    try:
        discounted_count = cache_manager.invalidate_discounted_products()
        top_selling_count = cache_manager.invalidate_top_selling_products()
        store_best_count = cache_manager.invalidate_store_best_items()
        
        total_count = discounted_count + top_selling_count + store_best_count
        logger.debug(f"모든 KOK 캐시 무효화 성공: 총 삭제된 키 수={total_count}")
        logger.info(f"모든 KOK 캐시 무효화 완료: 총 삭제된 키 수={total_count}")
        return {
            "message": f"모든 KOK 캐시가 무효화되었습니다.",
            "deleted_keys": {
                "discounted_products": discounted_count,
                "top_selling_products": top_selling_count,
                "store_best_items": store_best_count,
                "total": total_count
            }
        }
    except Exception as e:
        logger.error(f"모든 KOK 캐시 무효화 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")
        