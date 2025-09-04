"""
콕 쇼핑몰 DB 접근(CRUD) 함수 (MariaDB)

계층별 역할:
- 이 파일은 데이터 액세스 계층(Data Access Layer)을 담당
- ORM(Session)과 직접 상호작용하여 DB 상태 변경 로직 처리
- db.add(), db.delete() 같은 DB 상태 변경은 여기서 수행
- 트랜잭션 관리(commit/rollback)는 상위 계층(라우터)에서 담당
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta

from common.logger import get_logger
from common.keyword_extraction import load_ing_vocab, extract_ingredient_keywords, get_homeshopping_db_config

from services.order.models.order_model import Order, KokOrder
from services.kok.models.kok_model import (
    KokProductInfo, 
    KokImageInfo, 
    KokDetailInfo, 
    KokReviewExample, 
    KokPriceInfo, 
    KokSearchHistory,
    KokLikes,
    KokCart,
    KokNotification,
    KokClassify
)
from services.homeshopping.models.homeshopping_model import HomeshoppingClassify
from services.kok.schemas.kok_schema import (
    KokReviewStats,
    KokReviewDetail,
    KokReviewResponse,
    KokProductInfoResponse,
    KokProductTabsResponse,
    KokProductDetails,
    KokDetailInfoItem,
    KokProductDetailsResponse
)

logger = get_logger("kok_crud")


async def get_latest_kok_price_id(
        db: AsyncSession,
        kok_product_id: int
) -> Optional[int]:
    """
    주어진 kok_product_id에 대한 최신 가격 ID를 반환
    
    Args:
        db: 데이터베이스 세션
        kok_product_id: 상품 ID
        
    Returns:
        최신 가격 ID 또는 None
    """
    try:
        stmt = (
            select(func.max(KokPriceInfo.kok_price_id))
            .where(KokPriceInfo.kok_product_id == kok_product_id)
        )
        result = await db.execute(stmt)
        latest_price_id = result.scalar_one_or_none()
        
        if latest_price_id:
    # logger.info(f"최신 가격 ID 조회 완료: kok_product_id={kok_product_id}, latest_kok_price_id={latest_price_id}")
            return latest_price_id
        else:
            logger.warning(f"가격 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            return None
            
    except Exception as e:
        logger.error(f"최신 가격 ID 조회 중 오류 발생: kok_product_id={kok_product_id}, error={str(e)}")
        return None


async def get_kok_product_seller_details(
        db: AsyncSession,
        kok_product_id: int
) -> Optional[dict]:
    """
    상품의 상세정보를 반환
    - KOK_PRODUCT_INFO 테이블에서 판매자 정보
    - KOK_DETAIL_INFO 테이블에서 상세정보 목록
    """
    # logger.info(f"상품 판매자 정보 조회 시작: kok_product_id={kok_product_id}")
    
    # 1. KOK_PRODUCT_INFO 테이블에서 판매자 정보 조회
    product_stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_product_id)
    )
    try:
        product_result = await db.execute(product_stmt)
        product = product_result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"상품 판매자 정보 조회 SQL 실행 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise
    
    if not product:
        logger.warning(f"상품을 찾을 수 없음: kok_product_id={kok_product_id}")
        return None
    
    # 2. KOK_DETAIL_INFO 테이블에서 상세정보 목록 조회
    detail_stmt = (
        select(KokDetailInfo)
        .where(KokDetailInfo.kok_product_id == kok_product_id)
        .order_by(KokDetailInfo.kok_detail_col_id)
    )
    try:
        detail_result = await db.execute(detail_stmt)
        detail_infos = detail_result.scalars().all()
    except Exception as e:
        logger.warning(f"상품 상세정보 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        detail_infos = []
    
    # 3. 응답 데이터 구성
    seller_info_obj = KokProductDetails(
        kok_co_ceo=product.kok_co_ceo or "",
        kok_co_reg_no=product.kok_co_reg_no or "",
        kok_co_ec_reg=product.kok_co_ec_reg or "",
        kok_tell=product.kok_tell or "",
        kok_ver_item=product.kok_ver_item or "",
        kok_ver_date=product.kok_ver_date or "",
        kok_co_addr=product.kok_co_addr or "",
        kok_return_addr=product.kok_return_addr or "",
    )
    
    detail_info_objects = [
        KokDetailInfoItem(
            kok_detail_col_id=detail.kok_detail_col_id,
            kok_product_id=detail.kok_product_id,
            kok_detail_col=detail.kok_detail_col or "",
            kok_detail_val=detail.kok_detail_val or "",
        )
        for detail in detail_infos
    ]
    
    result = KokProductDetailsResponse(
        seller_info=seller_info_obj,
        detail_info=detail_info_objects
    )
    
    # logger.info(f"상품 판매자 정보 조회 완료: kok_product_id={kok_product_id}, 상세정보 수={len(detail_info_objects)}")
    return result
    

async def get_kok_product_list(
        db: AsyncSession,
        page: int = 1,
        size: int = 10,
        keyword: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
) -> Tuple[List[dict], int]:
    """
    콕 제품 목록을 반환 (페이지네이션, 검색, 정렬 지원)
    """
    offset = (page - 1) * size
    
    # 기본 쿼리
    stmt = select(KokProductInfo)
    
    # 키워드 검색
    if keyword:
        stmt = stmt.where(
            KokProductInfo.kok_product_name.contains(keyword) |
            KokProductInfo.kok_store_name.contains(keyword)
        )
    
    # 정렬
    if sort_by:
        if sort_by == "product_price":
            order_col = KokProductInfo.kok_product_price
        elif sort_by == "review_score":
            order_col = KokProductInfo.kok_review_score
        elif sort_by == "review_count":
            order_col = KokProductInfo.kok_review_cnt
        else:
            order_col = KokProductInfo.kok_product_id
        
        if sort_order == "desc":
            stmt = stmt.order_by(order_col.desc())
        else:
            stmt = stmt.order_by(order_col.asc())
    else:
        stmt = stmt.order_by(KokProductInfo.kok_product_id.desc())
    
    # 페이지네이션
    stmt = stmt.offset(offset).limit(size)
    
    try:
        products = (await db.execute(stmt)).scalars().all()
    except Exception as e:
        logger.error(f"콕 상품 목록 조회 SQL 실행 실패: page={page}, size={size}, keyword={keyword}, error={str(e)}")
        raise
    
    # 총 개수 조회
    count_stmt = select(func.count(KokProductInfo.kok_product_id))
    if keyword:
        count_stmt = count_stmt.where(
            KokProductInfo.kok_product_name.contains(keyword) |
            KokProductInfo.kok_store_name.contains(keyword)
        )
    try:
        total = (await db.execute(count_stmt)).scalar()
    except Exception as e:
        logger.error(f"콕 상품 개수 조회 SQL 실행 실패: keyword={keyword}, error={str(e)}")
        total = 0
    
    product_list = []
    for product in products:
        product_dict = {
            "kok_product_id": product.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_review_cnt": product.kok_review_cnt,
            "kok_review_score": product.kok_review_score,
            "kok_5_ratio": product.kok_5_ratio,
            "kok_4_ratio": product.kok_4_ratio,
            "kok_3_ratio": product.kok_3_ratio,
            "kok_2_ratio": product.kok_2_ratio,
            "kok_1_ratio": product.kok_1_ratio,
            "kok_aspect_price": product.kok_aspect_price,
            "kok_aspect_price_ratio": product.kok_aspect_price_ratio,
            "kok_aspect_delivery": product.kok_aspect_delivery,
            "kok_aspect_delivery_ratio": product.kok_aspect_delivery_ratio,
            "kok_aspect_taste": product.kok_aspect_taste,
            "kok_aspect_taste_ratio": product.kok_aspect_taste_ratio,
            "kok_seller": product.kok_seller,
            "kok_co_ceo": product.kok_co_ceo,
            "kok_co_reg_no": product.kok_co_reg_no,
            "kok_co_ec_reg": product.kok_co_ec_reg,
            "kok_tell": product.kok_tell,
            "kok_ver_item": product.kok_ver_item,
            "kok_ver_date": product.kok_ver_date,
            "kok_co_addr": product.kok_co_addr,
            "kok_return_addr": product.kok_return_addr,
            "kok_exchange_addr": product.kok_exchange_addr
        }
        product_list.append(product_dict)
    
    return product_list, total


# -----------------------------
# 메인화면 상품 리스트 함수
# -----------------------------

async def get_kok_discounted_products(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        use_cache: bool = True
) -> List[dict]:
    """
    할인 특가 상품 목록 조회 (할인율 높은 순으로 정렬)
    최적화: 단일 쿼리로 N+1 문제 해결 + Redis 캐싱
    """
    from services.kok.utils.cache_utils import cache_manager
    
    # logger.info(f"할인 상품 조회 시작: page={page}, size={size}, use_cache={use_cache}")
    
    # 캐시에서 데이터 조회 시도
    if use_cache:
        cached_data = cache_manager.get(
            'discounted_products',
            page=page,
            size=size
        )
        if cached_data:
    # logger.info(f"캐시에서 할인 상품 조회 완료: page={page}, size={size}, 결과 수={len(cached_data)}")
            return cached_data
    
    offset = (page - 1) * size
    
    # 서브쿼리로 각 상품의 최신 가격 ID를 구함
    latest_price_subquery = (
        select(
            KokPriceInfo.kok_product_id,
            func.max(KokPriceInfo.kok_price_id).label('latest_price_id')
        )
        .where(KokPriceInfo.kok_discount_rate > 0)
        .group_by(KokPriceInfo.kok_product_id)
        .subquery()
    )
    
    # 메인 쿼리: 상품 정보와 최신 가격 정보를 한 번에 조회
    stmt = (
        select(
            KokProductInfo,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price
        )
        .join(
            latest_price_subquery,
            KokProductInfo.kok_product_id == latest_price_subquery.c.kok_product_id
        )
        .join(
            KokPriceInfo,
            KokPriceInfo.kok_price_id == latest_price_subquery.c.latest_price_id
        )
        .order_by(KokPriceInfo.kok_discount_rate.desc())
        .offset(offset)
        .limit(size)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"할인 상품 조회 SQL 실행 실패: page={page}, size={size}, error={str(e)}")
        raise
    
    discounted_products = []
    for product, discount_rate, discounted_price in results:
        discounted_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
            "kok_review_cnt": product.kok_review_cnt,
            "kok_review_score": product.kok_review_score,
        })
    
    # 캐시에 데이터 저장
    if use_cache:
        cache_manager.set(
            'discounted_products',
            discounted_products,
            page=page,
            size=size
        )
    
    # logger.info(f"할인 상품 조회 완료: page={page}, size={size}, 결과 수={len(discounted_products)}")
    return discounted_products


async def get_kok_top_selling_products(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        sort_by: str = "review_count",  # "review_count" 또는 "rating"
        use_cache: bool = True
) -> List[dict]:
    """
    판매율 높은 상품 목록 조회 (정렬 기준에 따라 리뷰 개수 또는 별점 평균 순으로 정렬)
    최적화: 단일 쿼리로 N+1 문제 해결 + Redis 캐싱
    
    Args:
        db: 데이터베이스 세션
        page: 페이지 번호
        size: 페이지 크기
        sort_by: 정렬 기준 ("review_count": 리뷰 개수 순, "rating": 별점 평균 순)
        use_cache: 캐시 사용 여부
    """
    from services.kok.utils.cache_utils import cache_manager
    
    # logger.info(f"인기 상품 조회 시작: page={page}, size={size}, sort_by={sort_by}, use_cache={use_cache}")
    
    # 캐시에서 데이터 조회 시도
    if use_cache:
        cached_data = cache_manager.get(
            'top_selling_products',
            page=page,
            size=size,
            sort_by=sort_by
        )
        if cached_data:
    # logger.info(f"캐시에서 인기 상품 조회 완료: page={page}, size={size}, 결과 수={len(cached_data)}")
            return cached_data
    
    offset = (page - 1) * size
    
    # 서브쿼리로 각 상품의 최신 가격 ID를 구함
    latest_price_subquery = (
        select(
            KokPriceInfo.kok_product_id,
            func.max(KokPriceInfo.kok_price_id).label('latest_price_id')
        )
        .group_by(KokPriceInfo.kok_product_id)
        .subquery()
    )
    
    # 정렬 기준에 따라 쿼리 구성
    if sort_by == "rating":
        # 별점 평균 순으로 정렬 (리뷰가 있는 상품만)
        order_clause = [
            KokProductInfo.kok_review_score.desc(),
            KokProductInfo.kok_review_cnt.desc()
        ]
        where_conditions = [
            KokProductInfo.kok_review_cnt > 0,
            KokProductInfo.kok_review_score > 0
        ]
    else:
        # 기본값: 리뷰 개수 순으로 정렬
        order_clause = [
            KokProductInfo.kok_review_cnt.desc(),
            KokProductInfo.kok_review_score.desc()
        ]
        where_conditions = [
            KokProductInfo.kok_review_cnt > 0
        ]
    
    # 메인 쿼리: 상품 정보와 최신 가격 정보를 한 번에 조회
    stmt = (
        select(
            KokProductInfo,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price
        )
        .join(
            latest_price_subquery,
            KokProductInfo.kok_product_id == latest_price_subquery.c.kok_product_id
        )
        .join(
            KokPriceInfo,
            KokPriceInfo.kok_price_id == latest_price_subquery.c.latest_price_id
        )
        .where(*where_conditions)
        .order_by(*order_clause)
        .offset(offset)
        .limit(size)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"인기 상품 조회 SQL 실행 실패: page={page}, size={size}, sort_by={sort_by}, error={str(e)}")
        raise
    
    top_selling_products = []
    for product, discount_rate, discounted_price in results:
        top_selling_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": discount_rate or 0,
            "kok_discounted_price": discounted_price or product.kok_product_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
            "kok_review_cnt": product.kok_review_cnt,
            "kok_review_score": product.kok_review_score,
        })
    
    # 캐시에 데이터 저장
    if use_cache:
        cache_manager.set(
            'top_selling_products',
            top_selling_products,
            page=page,
            size=size,
            sort_by=sort_by
        )
    
    # logger.info(f"인기 상품 조회 완료: page={page}, size={size}, 결과 수={len(top_selling_products)}")
    return top_selling_products


async def get_kok_unpurchased(
        db: AsyncSession,
        user_id: int
) -> List[dict]:
    """
    미구매 상품 목록 조회 (최근 구매 상품과 중복되지 않는 상품)
    """
    # 1. 사용자의 최근 구매 상품 ID 목록 조회 (최근 30일)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    
    # Order와 KokOrder를 통해 구매한 상품 조회
    purchased_products_stmt = (
        select(KokOrder, Order)
        .join(Order, KokOrder.order_id == Order.order_id)
        .where(Order.user_id == user_id)
        .where(Order.order_time >= thirty_days_ago)
    )
    try:
        purchased_orders = (await db.execute(purchased_products_stmt)).all()
    except Exception as e:
        logger.error(f"사용자 구매 상품 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        return []
    
    # 구매한 상품 ID 목록 추출 (price_id를 통해 상품 정보 조회)
    purchased_product_ids = []
    for kok_order, order in purchased_orders:
        # kok_price_id를 통해 상품 정보 조회
        product_stmt = (
            select(KokPriceInfo.kok_product_id)
            .where(KokPriceInfo.kok_price_id == kok_order.kok_price_id)
        )
        try:
            product_result = await db.execute(product_stmt)
            product_id = product_result.scalar_one_or_none()
            if product_id:
                purchased_product_ids.append(product_id)
        except Exception as e:
            logger.warning(f"가격 ID로 상품 ID 조회 실패: kok_price_id={kok_order.kok_price_id}, error={str(e)}")
            continue
    
    # 2. 최근 구매 상품과 중복되지 않는 상품 중에서 추천 상품 선택
    # 조건: 리뷰 점수가 높고, 할인이 있는 상품 우선
    stmt = (
        select(KokProductInfo)
        .where(KokProductInfo.kok_review_score > 4.0)
        .where(KokProductInfo.kok_discount_rate > 0)
        .where(~KokProductInfo.kok_product_id.in_(purchased_product_ids))  # 구매하지 않은 상품만
        .order_by(KokProductInfo.kok_review_score.desc(), KokProductInfo.kok_discount_rate.desc())
        .limit(10)
    )
    
    try:
        products = (await db.execute(stmt)).scalars().all()
    except Exception as e:
        logger.error(f"미구매 상품 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        return []
    
    # 만약 조건에 맞는 상품이 10개 미만이면, 할인 조건을 제거하고 다시 조회
    if len(products) < 10:
        stmt = (
            select(KokProductInfo)
            .where(KokProductInfo.kok_review_score > 3.5)
            .where(~KokProductInfo.kok_product_id.in_(purchased_product_ids))
            .order_by(KokProductInfo.kok_review_score.desc())
            .limit(10)
        )
        try:
            products = (await db.execute(stmt)).scalars().all()
        except Exception as e:
            logger.error(f"미구매 상품 폴백 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
            return []
    
    return [product.__dict__ for product in products]


async def get_kok_store_best_items(
        db: AsyncSession,
        user_id: Optional[int] = None,
        sort_by: str = "review_count",  # "review_count" 또는 "rating"
        use_cache: bool = True
) -> List[dict]:
    """
    구매한 스토어의 베스트 상품 목록 조회 (정렬 기준에 따라 리뷰 개수 또는 별점 평균 순으로 정렬)
    최적화: 단일 쿼리로 N+1 문제 해결 + Redis 캐싱
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID (None이면 전체 베스트 상품 반환)
        sort_by: 정렬 기준 ("review_count": 리뷰 개수 순, "rating": 별점 평균 순)
        use_cache: 캐시 사용 여부
    """
    from services.kok.utils.cache_utils import cache_manager
    
    # logger.info(f"스토어 베스트 상품 조회 시작: user_id={user_id}, sort_by={sort_by}, use_cache={use_cache}")
    
    # 캐시에서 데이터 조회 시도
    if use_cache and user_id:
        cached_data = cache_manager.get(
            'store_best_items',
            user_id=user_id,
            sort_by=sort_by
        )
        if cached_data:
    # logger.info(f"캐시에서 스토어 베스트 상품 조회 완료: user_id={user_id}, 결과 수={len(cached_data)}")
            return cached_data
    
    if user_id:
        # 1. 사용자가 구매한 주문에서 price_id를 통해 상품 정보 조회
        stmt = (
            select(KokOrder, KokPriceInfo, KokProductInfo)
            .join(KokPriceInfo, KokOrder.kok_price_id == KokPriceInfo.kok_price_id)
            .join(KokProductInfo, KokPriceInfo.kok_product_id == KokProductInfo.kok_product_id)
            .join(Order, KokOrder.order_id == Order.order_id)
            .where(Order.user_id == user_id)
            .distinct()
        )
        try:
            results = (await db.execute(stmt)).all()
        except Exception as e:
            logger.error(f"사용자 구매 상품 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
            return []
        
        if not results:
            logger.warning(f"사용자가 구매한 상품이 없음: user_id={user_id}")
            return []
        
    # logger.info(f"사용자 구매 상품 조회 결과: user_id={user_id}, 구매 상품 수={len(results)}")
        
        # 2. 구매한 상품들의 판매자 정보 수집
        store_names = set()
        for order, price, product in results:
            if product.kok_store_name:
                store_names.add(product.kok_store_name)
                logger.debug(f"구매 상품: {product.kok_product_name}, 판매자: {product.kok_store_name}")
            else:
                logger.warning(f"구매 상품의 판매자 정보 누락: product_id={product.kok_product_id}, product_name={product.kok_product_name}")
        
    # logger.info(f"구매한 상품들의 판매자 정보: {store_names}, 판매자 수={len(store_names)}")
        
        if not store_names:
            logger.warning(f"구매한 상품의 판매자 정보가 없음: user_id={user_id}")
            return []
        
        # 3. 해당 판매자들이 판매중인 상품 중 정렬 기준에 따라 조회
        if sort_by == "rating":
            # 별점 평균 순으로 정렬 (리뷰가 있는 상품만)
            store_best_stmt = (
                select(KokProductInfo)
                .where(KokProductInfo.kok_store_name.in_(store_names))
                .where(KokProductInfo.kok_review_cnt > 0)
                .where(KokProductInfo.kok_review_score > 0)
                .order_by(KokProductInfo.kok_review_score.desc(), KokProductInfo.kok_review_cnt.desc())
                .limit(10)
            )
        else:
            # 기본값: 리뷰 개수 순으로 정렬
            store_best_stmt = (
                select(KokProductInfo)
                .where(KokProductInfo.kok_store_name.in_(store_names))
                .where(KokProductInfo.kok_review_cnt > 0)
                .order_by(KokProductInfo.kok_review_cnt.desc(), KokProductInfo.kok_review_score.desc())
                .limit(10)
            )
    else:
        # user_id가 없으면 전체 베스트 상품 조회
    # logger.info("전체 베스트 상품 조회 모드 (user_id 없음)")
        
        if sort_by == "rating":
            # 별점 평균 순으로 정렬 (리뷰가 있는 상품만)
            store_best_stmt = (
                select(KokProductInfo)
                .where(KokProductInfo.kok_review_cnt > 0)
                .where(KokProductInfo.kok_review_score > 0)
                .order_by(KokProductInfo.kok_review_score.desc(), KokProductInfo.kok_review_cnt.desc())
                .limit(10)
            )
            logger.debug("정렬 기준: 별점 높은 순 → 리뷰 개수 순")
        else:
            # 기본값: 리뷰 개수 순으로 정렬
            store_best_stmt = (
                select(KokProductInfo)
                .where(KokProductInfo.kok_review_cnt > 0)
                .order_by(KokProductInfo.kok_review_cnt.desc(), KokProductInfo.kok_review_score.desc())
                .limit(10)
            )
            logger.debug("정렬 기준: 리뷰 개수 순 → 별점 순")
    
    try:
        store_results = (await db.execute(store_best_stmt)).scalars().all()
    except Exception as e:
        logger.error(f"스토어 베스트 상품 조회 SQL 실행 실패: user_id={user_id}, sort_by={sort_by}, error={str(e)}")
        return []
    
    # logger.info(f"해당 판매자들의 현재 판매 상품 수: {len(store_results)}")
    if store_results:
        logger.debug(f"첫 번째 상품 정보: {store_results[0].kok_product_name}, 판매자: {store_results[0].kok_store_name}, 리뷰 수: {store_results[0].kok_review_cnt}")
    
    # 최적화: 상품 ID 목록을 추출하여 한 번에 가격 정보 조회
    product_ids = [product.kok_product_id for product in store_results]
    
    if not product_ids:
        logger.warning("조회된 상품이 없음")
        return []
    
    # 서브쿼리로 각 상품의 최신 가격 ID를 구함
    latest_price_subquery = (
        select(
            KokPriceInfo.kok_product_id,
            func.max(KokPriceInfo.kok_price_id).label('latest_price_id')
        )
        .where(KokPriceInfo.kok_product_id.in_(product_ids))
        .group_by(KokPriceInfo.kok_product_id)
        .subquery()
    )
    
    # 최신 가격 정보와 함께 상품 정보를 한 번에 조회
    optimized_stmt = (
        select(
            KokProductInfo,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price
        )
        .join(
            latest_price_subquery,
            KokProductInfo.kok_product_id == latest_price_subquery.c.kok_product_id
        )
        .join(
            KokPriceInfo,
            KokPriceInfo.kok_price_id == latest_price_subquery.c.latest_price_id
        )
        .where(KokProductInfo.kok_product_id.in_(product_ids))
    )
    
    try:
        optimized_results = (await db.execute(optimized_stmt)).all()
    except Exception as e:
        logger.error(f"스토어 베스트 상품 가격 정보 조회 SQL 실행 실패: user_id={user_id}, product_ids={product_ids[:5]}, error={str(e)}")
        return []
    
    # 결과를 딕셔너리로 변환하여 빠른 조회 가능하게 함
    product_price_map = {}
    for product, discount_rate, discounted_price in optimized_results:
        product_price_map[product.kok_product_id] = {
            'discount_rate': discount_rate,
            'discounted_price': discounted_price
        }
    
    store_best_products = []
    for product in store_results:
        price_info = product_price_map.get(product.kok_product_id)
        if price_info:
            store_best_products.append({
                "kok_product_id": product.kok_product_id,
                "kok_thumbnail": product.kok_thumbnail,
                "kok_discount_rate": price_info['discount_rate'] or 0,
                "kok_discounted_price": price_info['discounted_price'] or product.kok_product_price,
                "kok_product_name": product.kok_product_name,
                "kok_store_name": product.kok_store_name,
                "kok_review_cnt": product.kok_review_cnt,
                "kok_review_score": product.kok_review_score,
            })
    
    # 캐시에 데이터 저장 (user_id가 있는 경우만)
    if use_cache and user_id:
        cache_manager.set(
            'store_best_items',
            store_best_products,
            user_id=user_id,
            sort_by=sort_by
        )
    
    # logger.info(f"스토어 베스트 상품 조회 완료: user_id={user_id}, sort_by={sort_by}, 결과 수={len(store_best_products)}")
    
    # 최종 결과 요약 로그
    if store_best_products:
    # logger.info(f"반환된 상품들의 판매자 분포: {list(set([p['kok_store_name'] for p in store_best_products]))}")
    # logger.info(f"반환된 상품들의 리뷰 수 범위: {min([p['kok_review_cnt'] for p in store_best_products])} ~ {max([p['kok_review_cnt'] for p in store_best_products])}")
        pass
    else:
        logger.warning(f"빈 결과 반환 - 가능한 원인: 구매 이력 없음, 판매자 정보 누락, 해당 판매자 상품 없음, 리뷰 조건 불충족")
    
    return store_best_products


async def get_kok_product_by_id(
        db: AsyncSession,
        kok_product_id: int
) -> Optional[dict]:
    """
    제품 ID로 기본 제품 정보만 조회
    """
    stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_product_id)
    )
    try:
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"콕 상품 기본 정보 조회 SQL 실행 실패: kok_product_id={kok_product_id}, error={str(e)}")
        return None
    
    return product.__dict__ if product else None

async def get_kok_product_tabs(
        db: AsyncSession,
        kok_product_id: int
) -> Optional[List[dict]]:
    """
    상품 ID로 상품설명 이미지들 조회
    """
    # 상품 설명 이미지들 조회
    image_stmt = (
        select(KokImageInfo).where(KokImageInfo.kok_product_id == kok_product_id)
    )
    try:
        images_result = await db.execute(image_stmt)
        images = images_result.scalars().all()
    except Exception as e:
        logger.warning(f"상품 이미지 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        images = []
    
    images_list = []
    for img in images:
        # None 값 체크 및 기본값 설정
        if img.kok_img_id is not None:  # 필수 필드 체크
            images_list.append(KokImageInfo(
                kok_img_id=img.kok_img_id,
                kok_product_id=img.kok_product_id or kok_product_id,  # None이면 기본값 사용
                kok_img_url=img.kok_img_url or ""  # None이면 빈 문자열
            ))
    
    return KokProductTabsResponse(images=images_list)


async def get_kok_product_info(
        db: AsyncSession,
        kok_product_id: int,
        user_id: Optional[int] = None
) -> Optional[dict]:
    """
    상품 기본 정보 조회 (API 명세서 형식)
    """
    # logger.info(f"상품 기본 정보 조회 시작: kok_product_id={kok_product_id}, user_id={user_id}")
    
    stmt = (
        select(KokProductInfo)
        .where(KokProductInfo.kok_product_id == kok_product_id)
    )
    try:
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"콕 상품 정보 조회 SQL 실행 실패: kok_product_id={kok_product_id}, error={str(e)}")
        return None
    
    if not product:
        logger.warning(f"상품을 찾을 수 없음: kok_product_id={kok_product_id}")
        return None
    
    # 최신 가격 정보 조회
    latest_price_id = await get_latest_kok_price_id(db, kok_product_id)
    if latest_price_id:
        # 최신 가격 정보로 상세 정보 조회
        price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_price_id == latest_price_id)
        try:
            price_result = await db.execute(price_stmt)
            price = price_result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"가격 정보 조회 실패: kok_product_id={kok_product_id}, latest_price_id={latest_price_id}, error={str(e)}")
            price = None
    else:
        price = None
    
    # 찜 상태 확인
    is_liked = False
    if user_id:
        like_stmt = select(KokLikes).where(
            KokLikes.user_id == user_id,
            KokLikes.kok_product_id == product.kok_product_id
        )
        try:
            like_result = await db.execute(like_stmt)
            is_liked = like_result.scalar_one_or_none() is not None
        except Exception as e:
            logger.warning(f"찜 상태 확인 실패: user_id={user_id}, kok_product_id={kok_product_id}, error={str(e)}")
            is_liked = False
    
    # logger.info(f"상품 기본 정보 조회 완료: kok_product_id={kok_product_id}, user_id={user_id}, is_liked={is_liked}")
    
    return KokProductInfoResponse(
        kok_product_id=product.kok_product_id,
        kok_product_name=product.kok_product_name or "",
        kok_store_name=product.kok_store_name or "",
        kok_thumbnail=product.kok_thumbnail or "",
        kok_product_price=product.kok_product_price or 0,
        kok_discount_rate=price.kok_discount_rate if price else 0,
        kok_discounted_price=price.kok_discounted_price if price else (product.kok_product_price or 0),
        kok_review_cnt=product.kok_review_cnt or 0,
        is_liked=is_liked
    )


async def get_kok_review_data(
        db: AsyncSession,
        kok_product_id: int
) -> Optional[dict]:
    """
    상품의 리뷰 통계 정보와 개별 리뷰 목록을 반환
    - KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보
    - KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록
    """
    # 1. KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보 조회
    product_stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_product_id)
    )
    try:
        product_result = await db.execute(product_stmt)
        product = product_result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"리뷰 데이터 조회 SQL 실행 실패: kok_product_id={kok_product_id}, error={str(e)}")
        return None
    
    if not product:
        logger.warning(f"리뷰 데이터를 위한 상품을 찾을 수 없음: kok_product_id={kok_product_id}")
        return None
    
    # 2. KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록 조회
    review_stmt = (
        select(KokReviewExample)
        .where(KokReviewExample.kok_product_id == kok_product_id)
        .order_by(KokReviewExample.kok_review_date.desc())
    )
    try:
        review_result = await db.execute(review_stmt)
        reviews = review_result.scalars().all()
    except Exception as e:
        logger.warning(f"리뷰 목록 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        reviews = []
    
    # 3. 응답 데이터 구성
    stats = KokReviewStats(
        kok_review_score=product.kok_review_score or 0.0,
        kok_review_cnt=product.kok_review_cnt or 0,
        kok_5_ratio=product.kok_5_ratio or 0,
        kok_4_ratio=product.kok_4_ratio or 0,
        kok_3_ratio=product.kok_3_ratio or 0,
        kok_2_ratio=product.kok_2_ratio or 0,
        kok_1_ratio=product.kok_1_ratio or 0,
        kok_aspect_price=product.kok_aspect_price or "",
        kok_aspect_price_ratio=product.kok_aspect_price_ratio or 0,
        kok_aspect_delivery=product.kok_aspect_delivery or "",
        kok_aspect_delivery_ratio=product.kok_aspect_delivery_ratio or 0,
        kok_aspect_taste=product.kok_aspect_taste or "",
        kok_aspect_taste_ratio=product.kok_aspect_taste_ratio or 0,
    )
    
    review_list = []
    for review in reviews:
        # None 값 체크 및 기본값 설정
        if review.kok_review_id is not None:  # 필수 필드 체크
            review_list.append(KokReviewDetail(
                kok_review_id=review.kok_review_id,
                kok_product_id=review.kok_product_id or kok_product_id,  # None이면 기본값 사용
                kok_nickname=review.kok_nickname or "",
                kok_review_date=review.kok_review_date or "",
                kok_review_score=review.kok_review_score or 0,
                kok_price_eval=review.kok_price_eval or "",
                kok_delivery_eval=review.kok_delivery_eval or "",
                kok_taste_eval=review.kok_taste_eval or "",
                kok_review_text=review.kok_review_text or "",
            ))
    
    return KokReviewResponse(
        stats=stats,
        reviews=review_list
    )


async def get_kok_products_by_ingredient(
    db: AsyncSession, 
    ingredient: str, 
    limit: int = 10
) -> List[dict]:
    """
    ingredient(예: 고춧가루)로 콕 상품을 LIKE 검색, 필드명 model 변수명과 100% 일치
    """
    stmt = (
        select(KokProductInfo)
        .where(KokProductInfo.kok_product_name.ilike(f"%{ingredient}%"))
        .limit(limit)
    )
    try:
        result = await db.execute(stmt)
        results = result.all()
    except Exception as e:
        logger.error(f"식재료 기반 상품 검색 SQL 실행 실패: ingredient={ingredient}, limit={limit}, error={str(e)}")
        return []

    products = []
    for product in results:
        # 최신 가격 정보 조회
        latest_price_id = await get_latest_kok_price_id(db, product.kok_product_id)
        if latest_price_id:
            # 최신 가격 정보로 상세 정보 조회
            price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_price_id == latest_price_id)
            try:
                price_result = await db.execute(price_stmt)
                price_info = price_result.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"식재료 상품 가격 정보 조회 실패: kok_product_id={product.kok_product_id}, latest_price_id={latest_price_id}, error={str(e)}")
                price_info = None
            
            products.append({
                "kok_product_id": product.kok_product_id,
                "kok_product_name": product.kok_product_name,
                "kok_thumbnail": product.kok_thumbnail,
                "kok_store_name": product.kok_store_name,
                "kok_product_price": product.kok_product_price,
                "kok_discount_rate": price_info.kok_discount_rate if price_info else 0,
                "kok_discounted_price": (
                    price_info.kok_discounted_price
                    if price_info and price_info.kok_discounted_price
                    else product.kok_product_price
                ),
                "kok_review_score": product.kok_review_score,
                "kok_review_cnt": product.kok_review_cnt,
                # 필요시 model에 정의된 추가 필드도 동일하게 추출
            })
    
    return products


# -----------------------------
# 찜 관련 CRUD 함수
# -----------------------------

async def toggle_kok_likes(
    db: AsyncSession,
    user_id: int,
    kok_product_id: int
) -> bool:
    """
    찜 등록/해제 토글
    """
    # logger.info(f"찜 토글 시작: user_id={user_id}, product_id={kok_product_id}")
    
    # 기존 찜 확인
    stmt = select(KokLikes).where(
        KokLikes.user_id == user_id,
        KokLikes.kok_product_id == kok_product_id
    )
    try:
        result = await db.execute(stmt)
        existing_like = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"찜 상태 확인 SQL 실행 실패: user_id={user_id}, kok_product_id={kok_product_id}, error={str(e)}")
        raise
    
    if existing_like:
        # 찜 해제
        await db.delete(existing_like)
    # logger.info(f"찜 해제 완료: user_id={user_id}, product_id={kok_product_id}")
        return False
    else:
        # 찜 등록
        created_at = datetime.now()
        
        new_like = KokLikes(
            user_id=user_id,
            kok_product_id=kok_product_id,
            kok_created_at=created_at
        )
        
        db.add(new_like)
    # logger.info(f"찜 등록 완료: user_id={user_id}, product_id={kok_product_id}")
        return True


async def get_kok_liked_products(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자가 찜한 상품 목록 조회
    """
    stmt = (
        select(KokLikes, KokProductInfo)
        .join(KokProductInfo, KokLikes.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokLikes.user_id == user_id)
        .order_by(KokLikes.kok_created_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"찜한 상품 목록 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    liked_products = []
    for like, product in results:
        # 최신 가격 정보 조회
        latest_price_id = await get_latest_kok_price_id(db, product.kok_product_id)
        if latest_price_id:
            # 최신 가격 정보로 상세 정보 조회
            price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_price_id == latest_price_id)
            try:
                price_result = await db.execute(price_stmt)
                price = price_result.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"찜한 상품 가격 정보 조회 실패: kok_product_id={product.kok_product_id}, latest_price_id={latest_price_id}, error={str(e)}")
                price = None
            
            liked_products.append({
                "kok_product_id": product.kok_product_id,
                "kok_product_name": product.kok_product_name,
                "kok_thumbnail": product.kok_thumbnail,
                "kok_product_price": product.kok_product_price,
                "kok_discount_rate": price.kok_discount_rate if price else 0,
                "kok_discounted_price": price.kok_discounted_price if price else product.kok_product_price,
                "kok_store_name": product.kok_store_name,
            })
    
    return liked_products


# -----------------------------
# 장바구니 관련 CRUD 함수
# -----------------------------

async def get_kok_cart_items(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자의 장바구니 상품 목록 조회
    """
    stmt = (
        select(KokCart, KokProductInfo, KokPriceInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .join(KokPriceInfo, KokCart.kok_price_id == KokPriceInfo.kok_price_id)
        .where(KokCart.user_id == user_id)
        .order_by(KokCart.kok_created_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"장바구니 상품 목록 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    cart_items = []
    for cart, product, price in results:
        cart_items.append({
            "kok_cart_id": cart.kok_cart_id,
            "kok_product_id": product.kok_product_id,
            "kok_price_id": cart.kok_price_id,
            "recipe_id": cart.recipe_id,
            "kok_product_name": product.kok_product_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_discount_rate": price.kok_discount_rate if price else 0,
            "kok_discounted_price": price.kok_discounted_price if price else product.kok_product_price,
            "kok_store_name": product.kok_store_name,
            "kok_quantity": cart.kok_quantity,
        })
    
    return cart_items


# 새로운 장바구니 CRUD 함수들
async def add_kok_cart(
    db: AsyncSession,
    user_id: int,
    kok_product_id: int,
    kok_quantity: int = 1,
    recipe_id: Optional[int] = None
) -> dict:
    """
    장바구니에 상품 추가 (자동으로 최신 가격 ID 사용)
    """
    # logger.info(f"장바구니 추가 시작: user_id={user_id}, kok_product_id={kok_product_id}, kok_quantity={kok_quantity}, recipe_id={recipe_id}")
    
    # recipe_id가 0이면 None으로 처리 (외래키 제약 조건 위반 방지)
    if recipe_id == 0:
        recipe_id = None
    # logger.info(f"recipe_id가 0이므로 None으로 처리")
    
    # 최신 가격 ID 자동 조회
    latest_price_id = await get_latest_kok_price_id(db, kok_product_id)
    if not latest_price_id:
        logger.warning(f"가격 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
        raise ValueError("상품의 가격 정보를 찾을 수 없습니다.")
    
    # logger.info(f"최신 가격 ID 사용: kok_product_id={kok_product_id}, latest_kok_price_id={latest_price_id}")
    
    # 기존 장바구니 항목 확인 (product_id만 고려)
    stmt = select(KokCart).where(
        KokCart.user_id == user_id,
        KokCart.kok_product_id == kok_product_id
    )
    try:
        result = await db.execute(stmt)
        existing_cart = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"기존 장바구니 항목 확인 SQL 실행 실패: user_id={user_id}, kok_product_id={kok_product_id}, error={str(e)}")
        raise
    
    if existing_cart:
        # 수량 업데이트
        existing_cart.kok_quantity += kok_quantity
    # logger.info(f"장바구니 수량 업데이트 완료: kok_cart_id={existing_cart.kok_cart_id}, new_quantity={existing_cart.kok_quantity}")
        return {
            "kok_cart_id": existing_cart.kok_cart_id,
            "message": f"장바구니 수량이 {existing_cart.kok_quantity}개로 업데이트되었습니다."
        }
    else:
        # 새 항목 추가
        created_at = datetime.now()
        
        new_cart = KokCart(
            user_id=user_id,
            kok_product_id=kok_product_id,
            kok_price_id=latest_price_id,
            kok_quantity=kok_quantity,
            kok_created_at=created_at,
            recipe_id=recipe_id
        )
        
        db.add(new_cart)
        # refresh는 commit 후에 호출해야 하므로 여기서는 제거
        # await db.refresh(new_cart)
        
    # logger.info(f"장바구니 새 항목 추가 완료: user_id={user_id}, kok_product_id={kok_product_id}, kok_price_id={latest_price_id}")
        return {
            "kok_cart_id": 0,  # commit 후에 실제 ID를 얻을 수 있음
            "message": "장바구니에 상품이 추가되었습니다."
        }


async def update_kok_cart_quantity(
    db: AsyncSession,
    user_id: int,
    kok_cart_id: int,
    kok_quantity: int
) -> dict:
    """
    장바구니 상품 수량 변경
    """
    # 장바구니 항목 확인
    stmt = (
        select(KokCart)
        .where(KokCart.kok_cart_id == kok_cart_id)
        .where(KokCart.user_id == user_id)
    )
    try:
        result = await db.execute(stmt)
        cart_item = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"장바구니 항목 확인 SQL 실행 실패: user_id={user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        raise
    
    if not cart_item:
        logger.warning(f"장바구니 항목을 찾을 수 없음: user_id={user_id}, kok_cart_id={kok_cart_id}")
        raise ValueError("장바구니 항목을 찾을 수 없습니다.")
    
    # 수량 변경
    cart_item.kok_quantity = kok_quantity
    
    return {
        "kok_cart_id": cart_item.kok_cart_id,
        "kok_price_id": cart_item.kok_price_id,
        "kok_quantity": cart_item.kok_quantity,
        "message": f"수량이 {kok_quantity}개로 변경되었습니다."
    }


async def delete_kok_cart_item(
    db: AsyncSession,
    user_id: int,
    kok_cart_id: int
) -> dict:
    """
    장바구니에서 상품 삭제
    """
    # 장바구니 항목 확인
    stmt = (
        select(KokCart)
        .where(KokCart.kok_cart_id == kok_cart_id)
        .where(KokCart.user_id == user_id)
    )
    try:
        result = await db.execute(stmt)
        cart_item = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"장바구니 항목 삭제 확인 SQL 실행 실패: user_id={user_id}, kok_cart_id={kok_cart_id}, error={str(e)}")
        return {"success": False, "message": "장바구니 항목 삭제 중 오류가 발생했습니다."}
    
    if not cart_item:
        logger.warning(f"삭제할 장바구니 항목을 찾을 수 없음: user_id={user_id}, kok_cart_id={kok_cart_id}")
        return {"success": False, "message": "장바구니 항목을 찾을 수 없습니다."}
    
    # 삭제할 항목 정보 저장
    deleted_info = {
        "kok_cart_id": cart_item.kok_cart_id,
        "kok_price_id": cart_item.kok_price_id,
        "kok_product_id": cart_item.kok_product_id,
        "kok_quantity": cart_item.kok_quantity
    }
    
    # 장바구니에서 삭제
    await db.delete(cart_item)
    
    return {
        "success": True,
        "message": "장바구니에서 상품이 삭제되었습니다.",
        "deleted_item": deleted_info
    }


# -----------------------------
# 검색 관련 CRUD 함수
# -----------------------------

async def search_kok_products(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    size: int = 20
) -> Tuple[List[dict], int]:
    """
    키워드로 콕 상품 검색
    """
    try:
    # logger.info(f"상품 검색 시작: keyword='{keyword}', page={page}, size={size}")
        offset = (page - 1) * size
        
        # 검색 쿼리
        stmt = (
            select(KokProductInfo)
            .where(
                KokProductInfo.kok_product_name.ilike(f"%{keyword}%") |
                KokProductInfo.kok_store_name.ilike(f"%{keyword}%")
            )
            .order_by(KokProductInfo.kok_product_id.desc())
            .offset(offset)
            .limit(size)
        )
        
        try:
            results = (await db.execute(stmt)).scalars().all()
        except Exception as e:
            logger.error(f"상품 검색 SQL 실행 실패: keyword={keyword}, page={page}, size={size}, error={str(e)}")
            raise
        
        # 총 개수 조회
        count_stmt = (
            select(func.count(KokProductInfo.kok_product_id))
            .where(
                KokProductInfo.kok_product_name.ilike(f"%{keyword}%") |
                KokProductInfo.kok_store_name.ilike(f"%{keyword}%")
            )
        )
        try:
            total = (await db.execute(count_stmt)).scalar()
        except Exception as e:
            logger.error(f"상품 검색 개수 조회 SQL 실행 실패: keyword={keyword}, error={str(e)}")
            total = 0
        
        # 결과 변환
        products = []
        for product in results:
            # 최신 가격 정보 조회
            latest_price_id = await get_latest_kok_price_id(db, product.kok_product_id)
            if latest_price_id:
                # 최신 가격 정보로 상세 정보 조회
                price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_price_id == latest_price_id)
                try:
                    price_result = await db.execute(price_stmt)
                    price = price_result.scalar_one_or_none()
                except Exception as e:
                    logger.warning(f"검색 상품 가격 정보 조회 실패: kok_product_id={product.kok_product_id}, latest_price_id={latest_price_id}, error={str(e)}")
                    price = None
                
                products.append({
                    "kok_product_id": product.kok_product_id,
                    "kok_product_name": product.kok_product_name,
                    "kok_store_name": product.kok_store_name,
                    "kok_thumbnail": product.kok_thumbnail,
                    "kok_product_price": product.kok_product_price,
                    "kok_discount_rate": price.kok_discount_rate if price else 0,
                    "kok_discounted_price": price.kok_discounted_price if price else product.kok_product_price,
                    "kok_review_cnt": product.kok_review_cnt,
                    "kok_review_score": product.kok_review_score,
                })
        
    # logger.info(f"상품 검색 완료: keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
        return products, total
        
    except Exception as e:
        logger.error(f"상품 검색 중 오류 발생: keyword='{keyword}', error={str(e)}")
        raise Exception(f"상품 검색 중 데이터베이스 오류가 발생했습니다: {str(e)}")


async def get_kok_search_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 10
) -> List[dict]:
    """
    사용자의 검색 이력 조회
    """
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.user_id == user_id)
        .order_by(KokSearchHistory.kok_searched_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).scalars().all()
    except Exception as e:
        logger.error(f"검색 이력 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    return [
        {
            "kok_history_id": history.kok_history_id,
            "user_id": history.user_id,
            "kok_keyword": history.kok_keyword,
            "kok_searched_at": history.kok_searched_at,
        }
        for history in results
    ]

async def add_kok_search_history(
    db: AsyncSession,
    user_id: int,
    keyword: str
) -> dict:
    """
    검색 이력 추가
    """
    # logger.info(f"검색 이력 추가 시작: user_id={user_id}, keyword='{keyword}'")
    
    searched_at = datetime.now()
    
    new_history = KokSearchHistory(
        user_id=user_id,
        kok_keyword=keyword,
        kok_searched_at=searched_at
    )
    
    db.add(new_history)
    await db.flush()  # commit 전에 flush로 ID 생성
    await db.refresh(new_history)
    
    # logger.info(f"검색 이력 추가 완료: user_id={user_id}, keyword={keyword}, history_id={new_history.kok_history_id}")
    return {
        "kok_history_id": new_history.kok_history_id,
        "user_id": user_id,
        "kok_keyword": keyword,
        "kok_searched_at": searched_at,
    }


async def delete_kok_search_history(
    db: AsyncSession,
    user_id: int,
    kok_history_id: int
) -> bool:
    """
    특정 검색 이력 ID로 검색 이력 삭제
    """
    # logger.info(f"검색 이력 삭제 시작: user_id={user_id}, history_id={kok_history_id}")
    
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.user_id == user_id)
        .where(KokSearchHistory.kok_history_id == kok_history_id)
    )
    
    try:
        result = await db.execute(stmt)
        history = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"검색 이력 삭제 확인 SQL 실행 실패: user_id={user_id}, kok_history_id={kok_history_id}, error={str(e)}")
        return False
    
    if history:
        await db.delete(history)
    # logger.info(f"검색 이력 삭제 완료: user_id={user_id}, history_id={kok_history_id}")
        return True
    
    logger.warning(f"검색 이력을 찾을 수 없음: user_id={user_id}, history_id={kok_history_id}")
    return False


async def get_kok_notifications(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자의 알림 목록 조회
    """
    stmt = (
        select(KokNotification)
        .where(KokNotification.user_id == user_id)
        .order_by(KokNotification.created_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).scalars().all()
    except Exception as e:
        logger.error(f"알림 목록 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    notifications = []
    for notification in results:
        notifications.append({
            "notification_id": notification.notification_id,
            "user_id": notification.user_id,
            "kok_order_id": notification.kok_order_id,
            "status_id": notification.status_id,
            "title": notification.title,
            "message": notification.message,
            "created_at": notification.created_at
        })
    
    return notifications


async def get_ingredients_from_selected_cart_items(
    db: AsyncSession,
    user_id: int,
    selected_cart_ids: List[int]
) -> List[str]:
    """
    선택된 장바구니 상품들에서 재료명을 추출
    - 상품명에서 식재료 관련 키워드를 추출하여 반환
    - keyword_extraction.py의 로직을 사용하여 정확한 재료 추출
    """
    # logger.info(f"장바구니 상품에서 재료 추출 시작: user_id={user_id}, kok_cart_ids={selected_cart_ids}")

    if not selected_cart_ids:
        logger.warning("선택된 장바구니 항목이 없음")
        return []

    # 선택된 장바구니 상품들의 상품 정보 조회
    stmt = (
        select(KokCart, KokProductInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokCart.user_id == user_id)
        .where(KokCart.kok_cart_id.in_(selected_cart_ids))
    )

    try:
        result = await db.execute(stmt)
        cart_items = result.fetchall()
    except Exception as e:
        logger.error(f"선택된 장바구니 상품 조회 SQL 실행 실패: user_id={user_id}, kok_cart_ids={selected_cart_ids}, error={str(e)}")
        return []

    if not cart_items:
        logger.warning(f"장바구니 상품을 찾을 수 없음: user_id={user_id}, kok_cart_ids={selected_cart_ids}")
        return []

    # 표준 재료 어휘 로드 (TEST_MTRL.MATERIAL_NAME)
    ing_vocab = set()
    try:
        # 환경변수에서 자동으로 DB 설정을 가져와서 표준 재료 어휘 로드
        db_conf = get_homeshopping_db_config()
        ing_vocab = load_ing_vocab(db_conf)
    # logger.info(f"표준 재료 어휘 로드 완료: {len(ing_vocab)}개")
    except Exception as e:
        logger.error(f"표준 재료 어휘 로드 실패: {str(e)}")
    # logger.info("기본 키워드로 폴백하여 진행")
        # 실패 시 기본 키워드로 폴백
        ing_vocab = {
            "감자", "양파", "당근", "양배추", "상추", "시금치", "깻잎", "청경채", "브로콜리", "콜리플라워",
            "피망", "파프리카", "오이", "가지", "애호박", "고구마", "마늘", "생강", "대파", "쪽파",
            "돼지고기", "소고기", "닭고기", "양고기", "오리고기", "삼겹살", "목살", "등심", "안심",
            "새우", "고등어", "연어", "참치", "조기", "갈치", "꽁치", "고등어", "삼치", "전복",
            "홍합", "굴", "바지락", "조개", "새우", "게", "랍스터", "문어", "오징어", "낙지",
            "계란", "달걀", "우유", "치즈", "버터", "생크림", "요거트", "두부", "순두부", "콩나물",
            "숙주나물", "미나리", "깻잎", "상추", "치커리", "로메인", "아이스버그", "양상추", "적상추",
            "청상추", "배추", "무", "순무", "우엉", "연근", "토란", "토마토", "가지", "애호박",
            "호박", "단호박", "단감", "사과", "배", "복숭아", "자두", "포도", "딸기", "블루베리",
            "라즈베리", "블랙베리", "크랜베리", "오렌지", "레몬", "라임", "자몽", "귤", "한라봉",
            "천혜향", "레드향", "금귤", "유자", "석류", "무화과", "대추", "밤", "호두", "아몬드",
            "땅콩", "해바라기씨", "호박씨", "참깨", "들깨", "깨", "소금", "설탕", "간장", "된장",
            "고추장", "쌈장", "초고추장", "마요네즈", "케찹", "머스타드", "와사비", "겨자", "식초",
            "레몬즙", "라임즙", "올리브오일", "식용유", "참기름", "들기름", "고추기름", "마늘기름"
        }

    # 키워드 추출 로직 import
    extracted_ingredients = set()

    # 각 상품명에서 재료 키워드 추출
    for cart_item, product_info in cart_items:
        product_name = product_info.kok_product_name
        if not product_name:
            continue

    # logger.info(f"상품명 분석 중: {product_name}")

        try:
            # keyword_extraction.py의 고급 로직으로 재료 추출
            result = extract_ingredient_keywords(
                product_name=product_name,
                ing_vocab=ing_vocab,
                use_bigrams=True,      # 다단어 재료 매칭
                drop_first_token=True, # 브랜드명 제거
                strip_digits=True,     # 숫자/프로모션 제거
                keep_longest_only=True, # 가장 긴 키워드 우선
                max_fuzzy_try=1,       # 퍼지 매칭 시도 수 줄이기
                fuzzy_limit=1,         # 퍼지 결과 수 줄이기
                fuzzy_threshold=90     # 퍼지 임계값 높이기
            )

            if result and result.get("keywords"):
                keywords = result["keywords"]
                # 최대 1개만 추출하도록 제한
                if len(keywords) > 1:
                    keywords = [keywords[0]]  # 첫 번째 키워드만 사용
                extracted_ingredients.update(keywords)
                # logger.info(f"상품 '{product_name}'에서 추출된 키워드: {keywords}")
            else:
                logger.error(f"상품 '{product_name}'에서 키워드 추출 실패")

        except Exception as e:
            logger.error(f"상품 '{product_name}' 키워드 추출 중 오류: {str(e)}")
            continue

    # 중복 제거 및 정렬
    final_ingredients = sorted(list(extracted_ingredients))
    # logger.info(f"최종 추출된 재료: {final_ingredients}")
    return final_ingredients


async def get_ingredients_from_cart_product_ids(
    db: AsyncSession,
    kok_product_ids: List[int],
    homeshopping_product_ids: List[int] = None,
    unified_product_ids: List[int] = None
) -> List[str]:
    """
    장바구니에서 선택한 상품들의 kok_product_id와 homeshopping_product_ids를 받아서 키워드를 추출
    - KOK 상품: KOK_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 홈쇼핑 상품: HOMESHOPPING_CLASSIFY 테이블에서 cls_ing이 1인 상품만 필터링
    - 통합 상품: 두 테이블 모두에서 cls_ing이 1인 상품을 찾아서 필터링
    - 해당 상품들의 product_name에서 키워드 추출
    - keyword_extraction.py의 고급 로직 사용
    
    Returns:
        List[str]: 추출된 키워드 목록
    """
    homeshopping_product_ids = homeshopping_product_ids or []
    unified_product_ids = unified_product_ids or []
    
    # 통합 파라미터가 있으면 기존 파라미터와 합치기
    if unified_product_ids:
        kok_product_ids = list(set(kok_product_ids + unified_product_ids))
        homeshopping_product_ids = list(set(homeshopping_product_ids + unified_product_ids))
    
    # logger.info(f"장바구니 상품 ID에서 재료 추출 시작: kok_product_ids={kok_product_ids}, homeshopping_product_ids={homeshopping_product_ids}")

    if not kok_product_ids and not homeshopping_product_ids:
        logger.warning("선택된 상품 ID가 없음")
        return []

    # KOK 상품 처리
    kok_products = []
    if kok_product_ids:
        stmt = (
            select(KokClassify)
            .where(KokClassify.product_id.in_(kok_product_ids))
            .where(KokClassify.cls_ing == 1)
        )
        try:
            result = await db.execute(stmt)
            kok_products = result.scalars().all()
            logger.info(f"KOK cls_ing이 1인 상품 {len(kok_products)}개 발견")
        except Exception as e:
            logger.error(f"KOK 상품 분류 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
            kok_products = []

    # 홈쇼핑 상품 처리
    homeshopping_products = []
    if homeshopping_product_ids:
        stmt = (
            select(HomeshoppingClassify)
            .where(HomeshoppingClassify.product_id.in_(homeshopping_product_ids))
            .where(HomeshoppingClassify.cls_ing == 1)
        )
        try:
            result = await db.execute(stmt)
            homeshopping_products = result.scalars().all()
            # logger.info(f"홈쇼핑 cls_ing=1인 상품 {len(homeshopping_products)}개 발견")
        except Exception as e:
            logger.error(f"홈쇼핑 상품 분류 조회 SQL 실행 실패: homeshopping_product_ids={homeshopping_product_ids}, error={str(e)}")
            homeshopping_products = []

    # 모든 상품을 하나의 리스트로 합치기
    all_products = list(kok_products) + list(homeshopping_products)
    
    # 분류된 상품이 없으면 FCT_KOK_PRODUCT_INFO에서 직접 상품명 조회 (폴백)
    if not all_products and kok_product_ids:
        logger.warning(f"분류된 상품을 찾을 수 없음: kok_product_ids={kok_product_ids}, homeshopping_product_ids={homeshopping_product_ids}")
        # logger.info("FCT_KOK_PRODUCT_INFO에서 직접 상품명 조회 시도 (폴백)")
        
        # FCT_KOK_PRODUCT_INFO에서 상품명 조회
        product_stmt = (
            select(KokProductInfo)
            .where(KokProductInfo.kok_product_id.in_(kok_product_ids))
        )
        try:
            product_result = await db.execute(product_stmt)
            products = product_result.scalars().all()
        except Exception as e:
            logger.error(f"폴백 상품명 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
            products = []
        
        if products:
            # KokClassify 형태로 변환
            for product in products:
                temp_classify = type('TempClassify', (), {
                    'product_id': product.kok_product_id,
                    'product_name': product.kok_product_name,
                    'cls_ing': 1  # 임시로 1로 설정
                })()
                all_products.append(temp_classify)
            
        # logger.info(f"FCT_KOK_PRODUCT_INFO에서 {len(all_products)}개 상품 발견 (폴백)")
        else:
            logger.warning(f"FCT_KOK_PRODUCT_INFO에서도 상품을 찾을 수 없음: kok_product_ids={kok_product_ids}")
    
    if not all_products:
        logger.warning(f"모든 방법으로 상품을 찾을 수 없음: kok_product_ids={kok_product_ids}, homeshopping_product_ids={homeshopping_product_ids}")
        return []

    # logger.info(f"총 {len(all_products)}개 상품에서 키워드 추출 시작")

    # 표준 재료 어휘 로드 (TEST_MTRL.MATERIAL_NAME)
    ing_vocab = set()
    try:
        # 환경변수에서 자동으로 DB 설정을 가져와서 표준 재료 어휘 로드
        db_conf = get_homeshopping_db_config()
        ing_vocab = load_ing_vocab(db_conf)
        # logger.info(f"표준 재료 어휘 로드 완료: {len(ing_vocab)}개")
    except Exception as e:
        logger.error(f"표준 재료 어휘 로드 실패: {str(e)}")
        # logger.info("기본 키워드로 폴백하여 진행")
        # 실패 시 기본 키워드로 폴백
        ing_vocab = {
            "감자", "양파", "당근", "양배추", "상추", "시금치", "깻잎", "청경채", "브로콜리", "콜리플라워",
            "피망", "파프리카", "오이", "가지", "애호박", "고구마", "마늘", "생강", "대파", "쪽파",
            "돼지고기", "소고기", "닭고기", "양고기", "오리고기", "삼겹살", "목살", "등심", "안심",
            "새우", "고등어", "연어", "참치", "조기", "갈치", "꽁치", "고등어", "삼치", "전복",
            "홍합", "굴", "바지락", "조개", "새우", "게", "랍스터", "문어", "오징어", "낙지",
            "계란", "달걀", "우유", "치즈", "버터", "생크림", "요거트", "두부", "순두부", "콩나물",
            "숙주나물", "미나리", "깻잎", "상추", "치커리", "로메인", "아이스버그", "양상추", "적상추",
            "청상추", "배추", "무", "순무", "우엉", "연근", "토란", "토마토", "가지", "애호박",
            "호박", "단호박", "단감", "사과", "배", "복숭아", "자두", "포도", "딸기", "블루베리",
            "라즈베리", "블랙베리", "크랜베리", "오렌지", "레몬", "라임", "자몽", "귤", "한라봉",
            "천혜향", "레드향", "금귤", "유자", "석류", "무화과", "대추", "밤", "호두", "아몬드",
            "땅콩", "해바라기씨", "호박씨", "참깨", "들깨", "깨", "소금", "설탕", "간장", "된장",
            "고추장", "쌈장", "초고추장", "마요네즈", "케찹", "머스타드", "와사비", "겨자", "식초",
            "레몬즙", "라임즙", "올리브오일", "식용유", "참기름", "들기름", "고추기름", "마늘기름"
        }

    # 키워드 추출 로직
    extracted_ingredients = set()

    # 각 상품명에서 재료 키워드 추출
    for classified_product in all_products:
        product_name = classified_product.product_name
        if not product_name:
            continue

    # logger.info(f"상품명 분석 중: {product_name}")

        try:
            # keyword_extraction.py의 고급 로직으로 재료 추출
            result = extract_ingredient_keywords(
                product_name=product_name,
                ing_vocab=ing_vocab,
                use_bigrams=True,      # 다단어 재료 매칭
                drop_first_token=True, # 브랜드명 제거
                strip_digits=True,     # 숫자/프로모션 제거
                keep_longest_only=True, # 가장 긴 키워드 우선
                max_fuzzy_try=1,       # 퍼지 매칭 시도 수 줄이기
                fuzzy_limit=1,         # 퍼지 결과 수 줄이기
                fuzzy_threshold=90     # 퍼지 임계값 높이기
            )

            if result and result.get("keywords"):
                keywords = result["keywords"]
                # 최대 1개만 추출하도록 제한
                if len(keywords) > 1:
                    keywords = [keywords[0]]  # 첫 번째 키워드만 사용
                extracted_ingredients.update(keywords)
                
                # 키워드만 추출하여 저장
                # logger.info(f"상품 '{product_name}'에서 추출된 키워드: {keywords}")
            else:
                logger.error(f"상품 '{product_name}'에서 키워드 추출 실패")
                
        except Exception as e:
            logger.error(f"상품 '{product_name}' 키워드 추출 중 오류: {str(e)}")
            continue

    # 중복 제거 및 정렬
    final_ingredients = sorted(list(extracted_ingredients))
    # logger.info(f"최종 추출된 재료: {final_ingredients}")
    return final_ingredients


async def get_cart_product_names_by_ids(
    db: AsyncSession,
    kok_product_ids: List[int]
) -> List[str]:
    """
    kok_product_id 목록으로 상품명 목록을 조회
    """
    if not kok_product_ids:
        return []

    stmt = (
        select(KokProductInfo.kok_product_name)
        .where(KokProductInfo.kok_product_id.in_(kok_product_ids))
        .where(KokProductInfo.kok_product_name.isnot(None))
    )
    
    try:
        result = await db.execute(stmt)
        product_names = [row[0] for row in result.fetchall() if row[0]]
    except Exception as e:
        logger.error(f"상품명 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
        return []
    
    return product_names
