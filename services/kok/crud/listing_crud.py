from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.order.models.order_base_model import Order
from services.order.models.kok.kok_order_model import KokOrder
from services.kok.models.product_model import KokPriceInfo, KokProductInfo

from .shared import get_latest_kok_price_id, logger

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

async def get_kok_discounted_products_baseline(
        db: AsyncSession,
        page: int = 1,
        size: int = 20
) -> List[dict]:
    """
    할인 특가 상품 목록 조회 (Baseline: N+1 패턴)

    목적:
        - 부하 테스트에서 "최적화 전" 기준선 재현

    특징:
        - 상품 목록 조회 후 상품별 최신 가격을 추가 조회하는 N+1 패턴 유지
        - 캐시 미적용
    """
    offset = (page - 1) * size

    # 기준선(Baseline): 상품 목록 조회(1) + 상품별 최신 가격/상세 조회(N)
    # 주의: ONLY_FULL_GROUP_BY 환경에서도 동작하도록, 집계는 가격 테이블에서만 수행 후 상품 테이블과 조인함.
    max_discount_subquery = (
        select(
            KokPriceInfo.kok_product_id,
            func.max(KokPriceInfo.kok_discount_rate).label("max_discount_rate"),
        )
        .where(KokPriceInfo.kok_discount_rate > 0)
        .group_by(KokPriceInfo.kok_product_id)
        .subquery()
    )

    stmt = (
        select(KokProductInfo, max_discount_subquery.c.max_discount_rate)
        .join(
            max_discount_subquery,
            KokProductInfo.kok_product_id == max_discount_subquery.c.kok_product_id
        )
        .order_by(max_discount_subquery.c.max_discount_rate.desc())
        .offset(offset)
        .limit(size)
    )

    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"[baseline] 할인 상품 조회 SQL 실행 실패: page={page}, size={size}, error={str(e)}")
        raise

    discounted_products: List[dict] = []
    for product, _max_discount_rate in results:
        latest_price_id = await get_latest_kok_price_id(db, product.kok_product_id)
        if not latest_price_id:
            continue

        price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_price_id == latest_price_id)
        try:
            price_result = await db.execute(price_stmt)
            price_info = price_result.scalar_one_or_none()
        except Exception as e:
            logger.warning(
                f"[baseline] 가격 정보 조회 실패: kok_product_id={product.kok_product_id}, "
                f"latest_price_id={latest_price_id}, error={str(e)}"
            )
            price_info = None

        if not price_info:
            continue

        discounted_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": price_info.kok_discount_rate,
            "kok_discounted_price": price_info.kok_discounted_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
            "kok_review_cnt": product.kok_review_cnt,
            "kok_review_score": product.kok_review_score,
        })

    return discounted_products


async def get_kok_discounted_products(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        use_cache: bool = True
) -> List[dict]:
    """
    할인 특가 상품 목록 조회 (할인율 높은 순으로 정렬)
    비교용 쿼리 방식: Window 함수 + 페이지 단위 캐싱
    """
    from services.kok.utils.cache_utils import cache_manager
    
    # logger.info(f"할인 상품 조회 시작: page={page}, size={size}, use_cache={use_cache}")
    
    # 페이지 단위 캐시 조회
    if use_cache:
        cached_data = cache_manager.get('discounted_products', page=page, size=size)
        if cached_data:
            # logger.info(f"캐시에서 할인 상품 조회 완료: page={page}, size={size}, 결과 수={len(cached_data)}")
            return cached_data
    
    offset = (page - 1) * size
    
    # 윈도우 함수 기반 조회
    # 1. 상품별 최신 가격 후보 row에 rn 부여
    windowed_query = (
        select(
            KokProductInfo.kok_product_id,
            KokProductInfo.kok_thumbnail,
            KokProductInfo.kok_product_name,
            KokProductInfo.kok_store_name,
            KokProductInfo.kok_product_price,
            KokProductInfo.kok_review_cnt,
            KokProductInfo.kok_review_score,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price,
            func.row_number().over(
                partition_by=KokPriceInfo.kok_product_id,
                order_by=KokPriceInfo.kok_price_id.desc()
            ).label('rn')
        )
        .join(
            KokPriceInfo,
            KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id
        )
        .where(KokPriceInfo.kok_discount_rate > 0)
        .order_by(KokPriceInfo.kok_discount_rate.desc())
    )
    
    # 2. rn = 1인 row만 선택 후 페이징 적용
    subquery = windowed_query.subquery()
    stmt = (
        select(
            subquery.c.kok_product_id,
            subquery.c.kok_thumbnail,
            subquery.c.kok_product_name,
            subquery.c.kok_store_name,
            subquery.c.kok_product_price,
            subquery.c.kok_review_cnt,
            subquery.c.kok_review_score,
            subquery.c.kok_discount_rate,
            subquery.c.kok_discounted_price
        )
        .select_from(subquery)
        .where(subquery.c.rn == 1)
        .order_by(subquery.c.kok_discount_rate.desc())
        .offset(offset)
        .limit(size)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"할인 상품 조회 SQL 실행 실패: page={page}, size={size}, error={str(e)}")
        raise
    
    discounted_products = []
    for row in results:
        discounted_products.append({
            "kok_product_id": row.kok_product_id,
            "kok_thumbnail": row.kok_thumbnail,
            "kok_discount_rate": row.kok_discount_rate,
            "kok_discounted_price": row.kok_discounted_price,
            "kok_product_name": row.kok_product_name,
            "kok_store_name": row.kok_store_name,
            "kok_review_cnt": row.kok_review_cnt,
            "kok_review_score": row.kok_review_score,
        })
    
    # 페이지 단위 캐싱
    if use_cache:
        try:
            cache_manager.set('discounted_products', discounted_products, page=page, size=size)
        except Exception as e:
            logger.warning(f"페이지 캐싱 실패: {str(e)}")
    
    # logger.info(f"할인 상품 조회 완료: page={page}, size={size}, 결과 수={len(discounted_products)}")
    return discounted_products


async def get_kok_discounted_products_max_join(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        use_cache: bool = True
) -> List[dict]:
    """
    할인 특가 상품 목록 조회 (MAX ID 서브쿼리 + 조인)

    목적:
        - MariaDB 환경에서 윈도우 함수 대비 성능 비교

    특징:
        - 상품별 최신 가격 ID를 서브쿼리로 구한 뒤 조인
        - 옵션으로 캐시 사용 가능
    """
    from services.kok.utils.cache_utils import cache_manager

    if use_cache:
        cached_data = cache_manager.get('discounted_products', page=page, size=size)
        if cached_data:
            return cached_data

    offset = (page - 1) * size

    latest_price_subquery = (
        select(
            KokPriceInfo.kok_product_id,
            func.max(KokPriceInfo.kok_price_id).label("latest_price_id"),
        )
        .where(KokPriceInfo.kok_discount_rate > 0)
        .group_by(KokPriceInfo.kok_product_id)
        .subquery()
    )

    stmt = (
        select(
            KokProductInfo.kok_product_id,
            KokProductInfo.kok_thumbnail,
            KokProductInfo.kok_product_name,
            KokProductInfo.kok_store_name,
            KokProductInfo.kok_product_price,
            KokProductInfo.kok_review_cnt,
            KokProductInfo.kok_review_score,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price,
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
        logger.error(f"[max_join] 할인 상품 조회 SQL 실행 실패: page={page}, size={size}, error={str(e)}")
        raise

    discounted_products: List[dict] = []
    for row in results:
        discounted_products.append({
            "kok_product_id": row.kok_product_id,
            "kok_thumbnail": row.kok_thumbnail,
            "kok_discount_rate": row.kok_discount_rate,
            "kok_discounted_price": row.kok_discounted_price,
            "kok_product_name": row.kok_product_name,
            "kok_store_name": row.kok_store_name,
            "kok_review_cnt": row.kok_review_cnt,
            "kok_review_score": row.kok_review_score,
        })

    if use_cache:
        try:
            cache_manager.set('discounted_products', discounted_products, page=page, size=size)
        except Exception as e:
            logger.warning(f"[max_join] 캐시 저장 실패: {str(e)}")

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
    최적화: 윈도우 함수 사용 + 개선된 캐싱 전략 + 인덱스 최적화
    
    Args:
        db: 데이터베이스 세션
        page: 페이지 번호
        size: 페이지 크기
        sort_by: 정렬 기준 ("review_count": 리뷰 개수 순, "rating": 별점 평균 순)
        use_cache: 캐시 사용 여부
    """
    from services.kok.utils.cache_utils import cache_manager
    
    # logger.info(f"인기 상품 조회 시작: page={page}, size={size}, sort_by={sort_by}, use_cache={use_cache}")
    
    # 개선된 캐싱 전략: 전체 데이터를 캐시에서 조회
    if use_cache:
        cached_data = cache_manager.get('top_selling_products', page=page, size=size, sort_by=sort_by)
        if cached_data:
            # logger.info(f"캐시에서 인기 상품 조회 완료: page={page}, size={size}, 결과 수={len(cached_data)}")
            return cached_data
    
    offset = (page - 1) * size
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 복잡한 서브쿼리 제거
    # 1. 윈도우 함수로 최신 가격 정보를 직접 조회
    windowed_query = (
        select(
            KokProductInfo.kok_product_id,
            KokProductInfo.kok_thumbnail,
            KokProductInfo.kok_product_name,
            KokProductInfo.kok_store_name,
            KokProductInfo.kok_product_price,
            KokProductInfo.kok_review_cnt,
            KokProductInfo.kok_review_score,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price,
            func.row_number().over(
                partition_by=KokPriceInfo.kok_product_id,
                order_by=KokPriceInfo.kok_price_id.desc()
            ).label('rn')
        )
        .join(
            KokPriceInfo,
            KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id
        )
    )
    
    # 정렬 기준에 따라 쿼리 구성
    if sort_by == "rating":
        # 별점 평균 순으로 정렬 (리뷰가 있는 상품만)
        windowed_query = windowed_query.where(
            KokProductInfo.kok_review_cnt > 0,
            KokProductInfo.kok_review_score > 0
        ).order_by(
            KokProductInfo.kok_review_score.desc(),
            KokProductInfo.kok_review_cnt.desc()
        )
    else:
        # 기본값: 리뷰 개수 순으로 정렬
        windowed_query = windowed_query.where(
            KokProductInfo.kok_review_cnt > 0
        ).order_by(
            KokProductInfo.kok_review_cnt.desc(),
            KokProductInfo.kok_review_score.desc()
        )
    
    # 2. 서브쿼리로 최신 가격만 필터링 (rn = 1)
    subquery = windowed_query.subquery()
    stmt = (
        select(
            subquery.c.kok_product_id,
            subquery.c.kok_thumbnail,
            subquery.c.kok_product_name,
            subquery.c.kok_store_name,
            subquery.c.kok_product_price,
            subquery.c.kok_review_cnt,
            subquery.c.kok_review_score,
            subquery.c.kok_discount_rate,
            subquery.c.kok_discounted_price
        )
        .select_from(subquery)
        .where(subquery.c.rn == 1)
        .offset(offset)
        .limit(size)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"인기 상품 조회 SQL 실행 실패: page={page}, size={size}, sort_by={sort_by}, error={str(e)}")
        raise
    
    top_selling_products = []
    for row in results:
        top_selling_products.append({
            "kok_product_id": row.kok_product_id,
            "kok_thumbnail": row.kok_thumbnail,
            "kok_discount_rate": row.kok_discount_rate or 0,
            "kok_discounted_price": row.kok_discounted_price or row.kok_product_price,
            "kok_product_name": row.kok_product_name,
            "kok_store_name": row.kok_store_name,
            "kok_review_cnt": row.kok_review_cnt,
            "kok_review_score": row.kok_review_score,
        })
    
    # 개선된 캐싱: 전체 데이터를 캐시에 저장 (페이지별 캐싱 대신)
    if use_cache:
        # 전체 데이터를 조회하여 캐시에 저장
        all_subquery = windowed_query.subquery().alias('cache_subquery')
        all_data_stmt = (
            select(
                all_subquery.c.kok_product_id,
                all_subquery.c.kok_thumbnail,
                all_subquery.c.kok_product_name,
                all_subquery.c.kok_store_name,
                all_subquery.c.kok_product_price,
                all_subquery.c.kok_review_cnt,
                all_subquery.c.kok_review_score,
                all_subquery.c.kok_discount_rate,
                all_subquery.c.kok_discounted_price
            )
            .select_from(all_subquery)
            .where(all_subquery.c.rn == 1)
        )
        
        try:
            all_results = (await db.execute(all_data_stmt)).all()
            all_products = []
            for row in all_results:
                all_products.append({
                    "kok_product_id": row.kok_product_id,
                    "kok_thumbnail": row.kok_thumbnail,
                    "kok_discount_rate": row.kok_discount_rate or 0,
                    "kok_discounted_price": row.kok_discounted_price or row.kok_product_price,
                    "kok_product_name": row.kok_product_name,
                    "kok_store_name": row.kok_store_name,
                    "kok_review_cnt": row.kok_review_cnt,
                    "kok_review_score": row.kok_review_score,
                })
            
            # 전체 데이터를 캐시에 저장 (TTL 5분)
            cache_manager.set('top_selling_products', all_products, page=page, size=size, sort_by=sort_by)
        except Exception as e:
            logger.warning(f"전체 데이터 캐싱 실패: {str(e)}")
    
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
        
        logger.info(f"사용자 구매 상품 조회 결과: user_id={user_id}, 구매 상품 수={len(results)}")
        
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
        logger.info("전체 베스트 상품 조회 모드 (user_id 없음)")
        
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
    
    logger.info(f"해당 판매자들의 현재 판매 상품 수: {len(store_results)}")
    if store_results:
        logger.debug(f"첫 번째 상품 정보: {store_results[0].kok_product_name}, 판매자: {store_results[0].kok_store_name}, 리뷰 수: {store_results[0].kok_review_cnt}")
    
    # 최적화: 윈도우 함수를 사용하여 상품 정보와 최신 가격 정보를 한 번에 조회
    product_ids = [product.kok_product_id for product in store_results]
    
    if not product_ids:
        logger.warning("조회된 상품이 없음")
        return []
    
    # 윈도우 함수를 사용한 최적화된 쿼리
    windowed_query = (
        select(
            KokProductInfo.kok_product_id,
            KokProductInfo.kok_thumbnail,
            KokProductInfo.kok_product_name,
            KokProductInfo.kok_store_name,
            KokProductInfo.kok_product_price,
            KokProductInfo.kok_review_cnt,
            KokProductInfo.kok_review_score,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price,
            func.row_number().over(
                partition_by=KokPriceInfo.kok_product_id,
                order_by=KokPriceInfo.kok_price_id.desc()
            ).label('rn')
        )
        .join(
            KokPriceInfo,
            KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id
        )
        .where(KokProductInfo.kok_product_id.in_(product_ids))
    )
    
    # 최신 가격만 필터링하여 조회
    subquery = windowed_query.subquery()
    optimized_stmt = (
        select(
            subquery.c.kok_product_id,
            subquery.c.kok_discount_rate,
            subquery.c.kok_discounted_price
        )
        .select_from(subquery)
        .where(subquery.c.rn == 1)
    )
    
    try:
        optimized_results = (await db.execute(optimized_stmt)).all()
    except Exception as e:
        logger.error(f"스토어 베스트 상품 가격 정보 조회 SQL 실행 실패: user_id={user_id}, product_ids={product_ids[:5]}, error={str(e)}")
        return []
    
    # 결과를 딕셔너리로 변환하여 빠른 조회 가능하게 함
    product_price_map = {}
    for row in optimized_results:
        product_price_map[row.kok_product_id] = {
            'discount_rate': row.kok_discount_rate,
            'discounted_price': row.kok_discounted_price
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


