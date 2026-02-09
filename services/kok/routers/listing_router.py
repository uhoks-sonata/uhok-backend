from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user_optional
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.kok.schemas.product_schema import (
    KokDiscountedProductsResponse,
    KokTopSellingProductsResponse,
    KokStoreBestProductsResponse,
)
from services.kok.crud.listing_crud import (
    get_kok_discounted_products,
    get_kok_discounted_products_baseline,
    get_kok_discounted_products_max_join,
    get_kok_top_selling_products,
    get_kok_store_best_items,
)

logger = get_logger("kok_router")
router = APIRouter()

@router.get("/discounted/baseline", response_model=KokDiscountedProductsResponse)
async def get_discounted_products_baseline(
        request: Request,
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회 (Baseline: N+1 패턴)
    - 부하 테스트에서 최적화 전 기준선 비교용 엔드포인트
    - 캐시 미적용
    """
    import time
    start_time = time.time()

    logger.debug(f"[baseline] 할인 상품 조회 시작: page={page}, size={size}")

    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None

    logger.info(f"[baseline] 할인 상품 조회 요청: user_id={user_id}, page={page}, size={size}")

    try:
        products = await get_kok_discounted_products_baseline(db, page=page, size=size)
        logger.debug(f"[baseline] 할인 상품 조회 성공: 결과 수={len(products)}")
    except Exception as e:
        logger.error(f"[baseline] 할인 상품 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="할인 상품 조회 중 오류가 발생했습니다.")

    execution_time = (time.time() - start_time) * 1000
    logger.info(f"[baseline] 할인 상품 조회 성능: user_id={user_id}, 실행시간={execution_time:.2f}ms, 결과 수={len(products)}")

    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="kok_discounted_products_view_baseline",
            event_data={
                "product_count": len(products),
                "execution_time_ms": round(execution_time, 2),
                "use_cache": False
            },
            **http_info
        )

    return KokDiscountedProductsResponse(products=products)


@router.get("/discounted", response_model=KokDiscountedProductsResponse)
@router.get("/discounted/window", response_model=KokDiscountedProductsResponse)
async def get_discounted_products(
        request: Request,
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        use_cache: bool = Query(True, description="캐시 사용 여부"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회 (Window 함수 방식)
    - 비교 테스트용 쿼리 방식 중 하나
    - `use_cache=true`일 때 페이지 단위 캐시 사용
    - `/discounted`와 `/discounted/window`는 동일 동작
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


@router.get("/discounted/max-join", response_model=KokDiscountedProductsResponse)
async def get_discounted_products_max_join(
        request: Request,
        page: int = Query(1, ge=1, description="페이지 번호"),
        size: int = Query(20, ge=1, le=100, description="페이지 크기"),
        use_cache: bool = Query(True, description="캐시 사용 여부"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    할인 특가 상품 리스트 조회 (MAX ID 서브쿼리 + 조인 방식)
    - 윈도우 함수 방식과 성능 비교용 엔드포인트
    - use_cache 파라미터로 캐시 사용 여부 제어
    """
    import time
    start_time = time.time()

    logger.debug(f"[max_join] 할인 상품 조회 시작: page={page}, size={size}, use_cache={use_cache}")

    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None

    logger.info(f"[max_join] 할인 상품 조회 요청: user_id={user_id}, page={page}, size={size}, use_cache={use_cache}")

    try:
        products = await get_kok_discounted_products_max_join(db, page=page, size=size, use_cache=use_cache)
        logger.debug(f"[max_join] 할인 상품 조회 성공: 결과 수={len(products)}")
    except Exception as e:
        logger.error(f"[max_join] 할인 상품 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="할인 상품 조회 중 오류가 발생했습니다.")

    execution_time = (time.time() - start_time) * 1000
    logger.info(f"[max_join] 할인 상품 조회 성능: user_id={user_id}, 실행시간={execution_time:.2f}ms, 결과 수={len(products)}")

    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="kok_discounted_products_view_max_join",
            event_data={
                "product_count": len(products),
                "execution_time_ms": round(execution_time, 2),
                "use_cache": use_cache
            },
            **http_info
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
