"""
콕 쇼핑몰 DB 접근(CRUD) 함수 (MariaDB)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple

from services.kok.models.kok_model import (
    KokProductInfo, 
    KokImageInfo, 
    KokDetailInfo, 
    KokReviewExample, 
    KokPriceInfo, 
    KokSearchHistory,
    KokLikes,
    KokCart
)

from services.order.models.order_model import KokOrder, Order

async def get_kok_product_detail(
        db: AsyncSession,
        product_id: int
) -> Optional[dict]:
    """
    주어진 product_id에 해당하는 콕 제품 상세정보와 관련 정보를 반환
    """
    stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == product_id)
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        return None
    
    # 이미지 정보 조회
    img_stmt = (
        select(KokImageInfo).where(KokImageInfo.kok_product_id == product_id)
    )
    images = (await db.execute(img_stmt)).scalars().all()
    
    # 상세 정보 조회
    detail_stmt = (
        select(KokDetailInfo).where(KokDetailInfo.kok_product_id == product_id)
    )
    detail_infos = (await db.execute(detail_stmt)).scalars().all()
    
    # 리뷰 예시 조회
    review_stmt = (
        select(KokReviewExample).where(KokReviewExample.kok_product_id == product_id)
    )
    review_examples = (await db.execute(review_stmt)).scalars().all()
    
    # 가격 정보 조회
    price_stmt = (
        select(KokPriceInfo).where(KokPriceInfo.kok_product_id == product_id)
    )
    price_infos = (await db.execute(price_stmt)).scalars().all()
    
    return {
        **product.__dict__,
        "images": [img.__dict__ for img in images],
        "detail_infos": [detail.__dict__ for detail in detail_infos],
        "review_examples": [review.__dict__ for review in review_examples],
        "price_infos": [price.__dict__ for price in price_infos],
    }


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
    
    products = (await db.execute(stmt)).scalars().all()
    
    # 총 개수 조회
    count_stmt = select(func.count(KokProductInfo.kok_product_id))
    if keyword:
        count_stmt = count_stmt.where(
            KokProductInfo.kok_product_name.contains(keyword) |
            KokProductInfo.kok_store_name.contains(keyword)
        )
    total = (await db.execute(count_stmt)).scalar()
    
    return [product.__dict__ for product in products], total

# -----------------------------
# 메인화면 상품 리스트 함수
# -----------------------------

async def get_kok_discounted_products(
        db: AsyncSession
) -> List[dict]:
    """
    할인 특가 상품 목록 조회 (할인율 높은 순으로 정렬)
    """
    # KokProductInfo와 KokPriceInfo를 JOIN해서 할인율 정보 가져오기
    stmt = (
        select(KokProductInfo, KokPriceInfo)
        .join(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokPriceInfo.kok_discount_rate > 0)
        .order_by(KokPriceInfo.kok_discount_rate.desc())
        .limit(20)
    )
    results = (await db.execute(stmt)).all()
    
    discounted_products = []
    for product, price_info in results:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        if price_info.kok_discount_rate and price_info.kok_discount_rate > 0:
            discounted_price = int(product.kok_product_price * (1 - price_info.kok_discount_rate / 100))
        
        discounted_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": price_info.kok_discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
        })
    
    return discounted_products

async def get_kok_top_selling_products(
        db: AsyncSession
) -> List[dict]:
    """
    판매율 높은 상품 목록 조회 (리뷰 개수 많은 순으로 정렬, 20개 반환)
    """
    # KokProductInfo와 KokPriceInfo를 LEFT JOIN해서 할인율 정보 가져오기
    stmt = (
        select(KokProductInfo, KokPriceInfo)
        .outerjoin(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokProductInfo.kok_review_cnt > 0)
        .order_by(KokProductInfo.kok_review_cnt.desc())
        .limit(20)
    )
    results = (await db.execute(stmt)).all()
    
    top_selling_products = []
    for product, price_info in results:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        discount_rate = 0
        if price_info and price_info.kok_discount_rate and price_info.kok_discount_rate > 0:
            discount_rate = price_info.kok_discount_rate
            discounted_price = int(product.kok_product_price * (1 - price_info.kok_discount_rate / 100))
        
        top_selling_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
        })
    
    return top_selling_products


async def get_kok_unpurchased(
        db: AsyncSession,
        user_id: int
) -> List[dict]:
    """
    미구매 상품 목록 조회 (최근 구매 상품과 중복되지 않는 상품)
    """
    # 1. 사용자의 최근 구매 상품 ID 목록 조회 (최근 30일)
    from datetime import datetime, timedelta
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    
    # Order와 KokOrder를 통해 구매한 상품 조회
    purchased_products_stmt = (
        select(KokOrder, Order)
        .join(Order, KokOrder.order_id == Order.order_id)
        .where(Order.user_id == user_id)
        .where(Order.order_time >= thirty_days_ago)
    )
    purchased_orders = (await db.execute(purchased_products_stmt)).all()
    
    # 구매한 상품 ID 목록 추출 (price_id를 통해 상품 정보 조회)
    purchased_product_ids = []
    for kok_order, order in purchased_orders:
        # price_id를 통해 상품 정보 조회
        product_stmt = (
            select(KokPriceInfo.kok_product_id)
            .where(KokPriceInfo.kok_price_id == kok_order.price_id)
        )
        product_result = await db.execute(product_stmt)
        product_id = product_result.scalar_one_or_none()
        if product_id:
            purchased_product_ids.append(product_id)
    
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
    
    products = (await db.execute(stmt)).scalars().all()
    
    # 만약 조건에 맞는 상품이 10개 미만이면, 할인 조건을 제거하고 다시 조회
    if len(products) < 10:
        stmt = (
            select(KokProductInfo)
            .where(KokProductInfo.kok_review_score > 3.5)
            .where(~KokProductInfo.kok_product_id.in_(purchased_product_ids))
            .order_by(KokProductInfo.kok_review_score.desc())
            .limit(10)
        )
        products = (await db.execute(stmt)).scalars().all()
    
    return [product.__dict__ for product in products]

async def get_kok_store_best_items(
        db: AsyncSession,
        user_id: int
) -> List[dict]:
    """
    구매한 스토어의 리뷰 많은 상품 목록 조회
    """
    # 1. 사용자가 구매한 주문에서 price_id를 통해 상품 정보 조회
    stmt = (
        select(KokOrder, KokPriceInfo, KokProductInfo)
        .join(KokPriceInfo, KokOrder.kok_price_id == KokPriceInfo.kok_price_id)
        .join(KokProductInfo, KokPriceInfo.kok_product_id == KokProductInfo.kok_product_id)
        .join(Order, KokOrder.order_id == Order.order_id)
        .where(Order.user_id == user_id)
        .distinct()
    )
    results = (await db.execute(stmt)).all()
    
    if not results:
        return []
    
    # 2. 구매한 상품들의 판매자 정보 수집
    store_names = set()
    for order, price, product in results:
        if product.kok_store_name:
            store_names.add(product.kok_store_name)
    
    if not store_names:
        return []
    
    # 3. 해당 판매자들이 판매중인 상품 중 리뷰 개수가 많은 순으로 10개 조회
    store_best_stmt = (
        select(KokProductInfo, KokPriceInfo)
        .outerjoin(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokProductInfo.kok_store_name.in_(store_names))
        .where(KokProductInfo.kok_review_cnt > 0)
        .order_by(KokProductInfo.kok_review_cnt.desc())
        .limit(10)
    )
    store_results = (await db.execute(store_best_stmt)).all()
    
    store_best_products = []
    for product, price_info in store_results:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        discount_rate = 0
        if price_info and price_info.kok_discount_rate and price_info.kok_discount_rate > 0:
            discount_rate = price_info.kok_discount_rate
            discounted_price = int(product.kok_product_price * (1 - price_info.kok_discount_rate / 100))
        
        store_best_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
        })
    
    return store_best_products


async def get_kok_product_by_id(
        db: AsyncSession,
        product_id: int
) -> Optional[dict]:
    """
    제품 ID로 기본 제품 정보만 조회
    """
    stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == product_id)
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    
    return product.__dict__ if product else None

async def get_kok_product_tabs(
        db: AsyncSession,
        product_id: int
) -> Optional[List[dict]]:
    """
    상품 ID로 상품설명 이미지들 조회
    """
    # 상품 설명 이미지들 조회
    image_stmt = (
        select(KokImageInfo).where(KokImageInfo.kok_product_id == product_id)
    )
    images_result = await db.execute(image_stmt)
    images = images_result.scalars().all()
    
    return [
        {
            "kok_img_id": img.kok_img_id,
            "kok_img_url": img.kok_img_url
        }
        for img in images
    ]


async def get_kok_product_info(
        db: AsyncSession,
        product_id: int
) -> Optional[dict]:
    """
    상품 기본 정보 조회 (API 명세서 형식)
    """
    stmt = (
        select(KokProductInfo, KokPriceInfo)
        .join(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokProductInfo.kok_product_id == product_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        return None
    
    product, price = row
    
    return {
        "kok_product_id": str(product.kok_product_id),
        "kok_product_name": product.kok_product_name,
        "kok_store_name": product.kok_store_name,
        "kok_thumbnail": product.kok_thumbnail,
        "kok_product_price": product.kok_product_price,
        "kok_discount_rate": price.kok_discount_rate if price else 0,
        "kok_discounted_price": price.kok_discounted_price if price else product.kok_product_price,
        "kok_review_cnt": product.kok_review_cnt or 0
    }

async def get_kok_review_data(
        db: AsyncSession,
        product_id: int
) -> Optional[dict]:
    """
    상품의 리뷰 통계 정보와 개별 리뷰 목록을 반환
    - KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보
    - KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록
    """
    # 1. KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보 조회
    product_stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == product_id)
    )
    product_result = await db.execute(product_stmt)
    product = product_result.scalar_one_or_none()
    
    if not product:
        return None
    
    # 2. KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록 조회
    review_stmt = (
        select(KokReviewExample)
        .where(KokReviewExample.kok_product_id == product_id)
        .order_by(KokReviewExample.kok_review_date.desc())
    )
    review_result = await db.execute(review_stmt)
    reviews = review_result.scalars().all()
    
    # 3. 응답 데이터 구성
    stats = {
        "kok_review_score": product.kok_review_score,
        "kok_review_cnt": product.kok_review_cnt,
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
    }
    
    review_list = [
        {
            "kok_review_id": review.kok_review_id,
            "kok_product_id": review.kok_product_id,
            "kok_nickname": review.kok_nickname,
            "kok_review_date": review.kok_review_date,
            "kok_review_score": review.kok_review_score,
            "kok_price_eval": review.kok_price_eval,
            "kok_delivery_eval": review.kok_delivery_eval,
            "kok_taste_eval": review.kok_taste_eval,
            "kok_review_text": review.kok_review_text,
        }
        for review in reviews
    ]
    
    return {
        "stats": stats,
        "reviews": review_list
    }

async def get_kok_products_by_ingredient(
    db: AsyncSession, 
    ingredient: str, 
    limit: int = 10
) -> List[dict]:
    """
    ingredient(예: 고춧가루)로 콕 상품을 LIKE 검색, 필드명 model 변수명과 100% 일치
    """
    stmt = (
        select(KokProductInfo, KokPriceInfo)
        .outerjoin(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokProductInfo.kok_product_name.ilike(f"%{ingredient}%"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    results = result.all()

    return [
        {
            "kok_product_id": p.kok_product_id,
            "kok_product_name": p.kok_product_name,
            "kok_thumbnail": p.kok_thumbnail,
            "kok_store_name": p.kok_store_name,
            "kok_product_price": p.kok_product_price,
            "kok_discount_rate": price.kok_discount_rate if price else 0,
            "kok_discounted_price": (
                price.kok_discounted_price
                if price and price.kok_discounted_price
                else p.kok_product_price
            ),
            "kok_review_score": p.kok_review_score,
            "kok_review_cnt": p.kok_review_cnt,
            # 필요시 model에 정의된 추가 필드도 동일하게 추출
        }
        for p, price in results
    ]

async def get_kok_product_details(
        db: AsyncSession,
        product_id: int
) -> Optional[dict]:
    """
    상품의 상세정보를 반환
    - KOK_PRODUCT_INFO 테이블에서 판매자 정보
    - KOK_DETAIL_INFO 테이블에서 상세정보 목록
    """
    # 1. KOK_PRODUCT_INFO 테이블에서 판매자 정보 조회
    product_stmt = (
        select(KokProductInfo).where(KokProductInfo.kok_product_id == product_id)
    )
    product_result = await db.execute(product_stmt)
    product = product_result.scalar_one_or_none()
    
    if not product:
        return None
    
    # 2. KOK_DETAIL_INFO 테이블에서 상세정보 목록 조회
    detail_stmt = (
        select(KokDetailInfo)
        .where(KokDetailInfo.kok_product_id == product_id)
        .order_by(KokDetailInfo.kok_detail_col_id)
    )
    detail_result = await db.execute(detail_stmt)
    detail_infos = detail_result.scalars().all()
    
    # 3. 응답 데이터 구성
    seller_info = {
        "kok_co_ceo": product.kok_co_ceo,
        "kok_co_reg_no": product.kok_co_reg_no,
        "kok_co_ec_reg": product.kok_co_ec_reg,
        "kok_tell": product.kok_tell,
        "kok_ver_item": product.kok_ver_item,
        "kok_ver_date": product.kok_ver_date,
        "kok_co_addr": product.kok_co_addr,
        "kok_return_addr": product.kok_return_addr,
    }
    
    detail_info_list = [
        {
            "kok_detail_col": detail.kok_detail_col,
            "kok_detail_val": detail.kok_detail_val,
        }
        for detail in detail_infos
    ]
    
    return {
        "seller_info": seller_info,
        "detail_info": detail_info_list
    }

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
    # 기존 찜 확인
    stmt = (
        select(KokLikes)
        .where(KokLikes.user_id == user_id)
        .where(KokLikes.kok_product_id == kok_product_id)
    )
    result = await db.execute(stmt)
    existing_like = result.scalar_one_or_none()
    
    if existing_like:
        # 찜 해제
        await db.delete(existing_like)
        await db.commit()
        return False
    else:
        # 찜 등록
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        new_like = KokLikes(
            user_id=user_id,
            kok_product_id=kok_product_id,
            kok_created_at=created_at
        )
        
        db.add(new_like)
        await db.commit()
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
        select(KokLikes, KokProductInfo, KokPriceInfo)
        .join(KokProductInfo, KokLikes.kok_product_id == KokProductInfo.kok_product_id)
        .join(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id, isouter=True)
        .where(KokLikes.user_id == user_id)
        .order_by(KokLikes.kok_created_at.desc())
        .limit(limit)
    )
    
    results = (await db.execute(stmt)).all()
    
    liked_products = []
    for like, product, price in results:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        discount_rate = 0
        if price and price.kok_discount_rate and price.kok_discount_rate > 0:
            discount_rate = price.kok_discount_rate
            discounted_price = int(product.kok_product_price * (1 - price.kok_discount_rate / 100))
        
        liked_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_discount_rate": discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_store_name": product.kok_store_name,
        })
    
    return liked_products

# -----------------------------
# 장바구니 관련 CRUD 함수
# -----------------------------

async def get_kok_cart_items(
    db: AsyncSession,
    user_id: int,
    limit: int = 100
) -> List[dict]:
    """
    사용자의 장바구니 상품 목록 조회
    """
    stmt = (
        select(
            KokCart.kok_cart_id,
            KokCart.kok_product_id,
            KokCart.kok_quantity,
            KokCart.kok_created_at,
            KokProductInfo.kok_product_name,
            KokProductInfo.kok_product_price,
            KokProductInfo.kok_thumbnail,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price
        )
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .outerjoin(KokPriceInfo, KokCart.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokCart.user_id == user_id)
        .order_by(KokCart.kok_created_at.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    cart_items = []
    for row in rows:
        cart_item = {
            "kok_cart_id": row.kok_cart_id,
            "kok_product_id": row.kok_product_id,
            "kok_product_name": row.kok_product_name,
            "kok_product_price": row.kok_product_price,
            "kok_quantity": row.kok_quantity,
            "kok_product_image": row.kok_thumbnail,
            "kok_discount_rate": row.kok_discount_rate or 0,
            "kok_discounted_price": row.kok_discounted_price or row.kok_product_price,
            "total_price": (row.kok_discounted_price or row.kok_product_price) * row.kok_quantity,
            "kok_created_at": row.kok_created_at
        }
        cart_items.append(cart_item)
    
    return cart_items

async def get_kok_cart_item(
    db: AsyncSession,
    user_id: int,
    cart_item_id: int
) -> Optional[dict]:
    """
    특정 장바구니 항목 조회
    """
    stmt = (
        select(
            KokCart.kok_cart_id,
            KokCart.kok_product_id,
            KokCart.kok_quantity,
            KokCart.kok_created_at,
            KokProductInfo.kok_product_name,
            KokProductInfo.kok_product_price,
            KokProductInfo.kok_thumbnail,
            KokPriceInfo.kok_discount_rate,
            KokPriceInfo.kok_discounted_price
        )
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .outerjoin(KokPriceInfo, KokCart.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokCart.user_id == user_id, KokCart.kok_cart_id == cart_item_id)
    )
    
    result = await db.execute(stmt)
    row = result.first()
    
    if not row:
        return None
    
    return {
        "kok_cart_id": row.kok_cart_id,
        "kok_product_id": row.kok_product_id,
        "kok_product_name": row.kok_product_name,
        "kok_product_price": row.kok_product_price,
        "kok_quantity": row.kok_quantity,
        "kok_product_image": row.kok_thumbnail,
        "kok_discount_rate": row.kok_discount_rate or 0,
        "kok_discounted_price": row.kok_discounted_price or row.kok_product_price,
        "total_price": (row.kok_discounted_price or row.kok_product_price) * row.kok_quantity,
        "kok_created_at": row.kok_created_at
    }

# 새로운 장바구니 CRUD 함수들
async def add_kok_cart(
    db: AsyncSession,
    user_id: int,
    kok_product_id: int,
    kok_quantity: int = 1
) -> dict:
    """
    장바구니에 상품 추가
    """
    # 제품 존재 여부 확인
    product_stmt = (
        select(KokProductInfo)
        .where(KokProductInfo.kok_product_id == kok_product_id)
    )
    product_result = await db.execute(product_stmt)
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise ValueError(f"제품 ID {kok_product_id}가 존재하지 않습니다.")
    
    # 기존 장바구니 항목 확인
    stmt = (
        select(KokCart)
        .where(KokCart.user_id == user_id)
        .where(KokCart.kok_product_id == kok_product_id)
    )
    result = await db.execute(stmt)
    existing_cart = result.scalar_one_or_none()
    
    if existing_cart:
        # 이미 장바구니에 있는 경우 수량 증가하지 않고 메시지만 반환
        return {
            "kok_cart_id": existing_cart.kok_cart_id,
            "message": "이미 장바구니에 있습니다."
        }
    else:
        # 새로운 상품 추가
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        new_cart = KokCart(
            user_id=user_id,
            kok_product_id=kok_product_id,
            kok_quantity=kok_quantity,
            kok_created_at=created_at
        )
        
        db.add(new_cart)
        await db.commit()
        await db.refresh(new_cart)
        
        return {
            "kok_cart_id": new_cart.kok_cart_id,
            "message": "장바구니에 추가되었습니다."
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
    result = await db.execute(stmt)
    cart_item = result.scalar_one_or_none()
    
    if not cart_item:
        raise ValueError("장바구니 항목을 찾을 수 없습니다.")
    
    # 수량 변경
    cart_item.kok_quantity = kok_quantity
    await db.commit()
    
    return {
        "kok_cart_id": cart_item.kok_cart_id,
        "kok_quantity": cart_item.kok_quantity,
        "message": f"수량이 {kok_quantity}개로 변경되었습니다."
    }


async def delete_kok_cart_item(
    db: AsyncSession,
    user_id: int,
    kok_cart_id: int
) -> bool:
    """
    장바구니에서 상품 삭제
    """
    # 장바구니 항목 확인
    stmt = (
        select(KokCart)
        .where(KokCart.kok_cart_id == kok_cart_id)
        .where(KokCart.user_id == user_id)
    )
    result = await db.execute(stmt)
    cart_item = result.scalar_one_or_none()
    
    if not cart_item:
        return False
    
    # 장바구니에서 삭제
    await db.delete(cart_item)
    await db.commit()
    return True



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
    offset = (page - 1) * size
    
    # 검색 쿼리
    stmt = (
        select(KokProductInfo, KokPriceInfo)
        .join(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id, isouter=True)
        .where(
            KokProductInfo.kok_product_name.ilike(f"%{keyword}%") |
            KokProductInfo.kok_store_name.ilike(f"%{keyword}%")
        )
        .order_by(KokProductInfo.kok_product_id.desc())
        .offset(offset)
        .limit(size)
    )
    
    results = (await db.execute(stmt)).all()
    
    # 총 개수 조회
    count_stmt = (
        select(func.count(KokProductInfo.kok_product_id))
        .where(
            KokProductInfo.kok_product_name.ilike(f"%{keyword}%") |
            KokProductInfo.kok_store_name.ilike(f"%{keyword}%")
        )
    )
    total = (await db.execute(count_stmt)).scalar()
    
    # 결과 변환
    products = []
    for product, price in results:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        discount_rate = 0
        if price and price.kok_discount_rate and price.kok_discount_rate > 0:
            discount_rate = price.kok_discount_rate
            discounted_price = int(product.kok_product_price * (1 - price.kok_discount_rate / 100))
        
        products.append({
            "kok_product_id": product.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_discount_rate": discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_review_cnt": product.kok_review_cnt,
            "kok_review_score": product.kok_review_score,
        })
    
    return products, total

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
    
    results = (await db.execute(stmt)).scalars().all()
    
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
    from datetime import datetime
    
    searched_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    new_history = KokSearchHistory(
        user_id=user_id,
        kok_keyword=keyword,
        kok_searched_at=searched_at
    )
    
    db.add(new_history)
    await db.commit()
    await db.refresh(new_history)
    
    return {
        "kok_history_id": new_history.kok_history_id,
        "user_id": new_history.user_id,
        "kok_keyword": new_history.kok_keyword,
        "kok_searched_at": new_history.kok_searched_at,
    }

async def delete_kok_search_history(
    db: AsyncSession,
    user_id: int,
    kok_history_id: int
) -> bool:
    """
    특정 검색 이력 ID로 검색 이력 삭제
    """
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.user_id == user_id)
        .where(KokSearchHistory.kok_history_id == kok_history_id)
    )
    
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()
    
    if history:
        await db.delete(history)
        await db.commit()
        return True
    
    return False

async def get_kok_notifications(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자의 콕 알림 내역을 조회
    - 주문완료, 배송출발, 배송완료 등의 알림을 조회
    """
    from services.kok.models.kok_model import KokNotification
    
    stmt = (
        select(KokNotification)
        .where(KokNotification.user_id == user_id)
        .order_by(KokNotification.created_at.desc())
        .limit(limit)
    )
    
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    
    return [
        {
            "notification_id": notification.notification_id,
            "user_id": notification.user_id,
            "kok_order_id": notification.kok_order_id,
            "status_id": notification.status_id,
            "title": notification.title,
            "message": notification.message,
            "created_at": notification.created_at.strftime("%Y-%m-%d %H:%M:%S") if notification.created_at else None
        }
        for notification in notifications
    ]



async def create_multiple_kok_orders_from_ids(
    db: AsyncSession,
    user_id: int,
    selected_items: List[dict]  # [{"cart_id": 1, "quantity": 2}, {"cart_id": 3, "quantity": 1}]
) -> dict:
    """
    선택된 장바구니 상품들로 여러 주문 생성 (동일한 주문 ID)
    프론트엔드에서 전송한 수량을 사용
    """
    if not selected_items:
        raise ValueError("선택된 상품이 없습니다.")

    from services.order.crud.order_crud import create_kok_order, initialize_status_master
    from services.order.models.order_model import Order, KokOrder
    from datetime import datetime

    # 상태 마스터 초기화
    await initialize_status_master(db)

    # 주문 생성
    order_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 메인 주문 생성
    main_order = Order(
        user_id=user_id,
        order_time=order_time,
        total_amount=0,  # 나중에 계산
        status_id=1  # 주문완료 상태
    )

    db.add(main_order)
    await db.commit()
    await db.refresh(main_order)

    # 선택된 상품들의 cart_id 추출
    selected_cart_ids = [item["cart_id"] for item in selected_items]
    
    # 선택된 장바구니 항목들과 상품 정보 조회
    stmt = (
        select(KokCart, KokProductInfo, KokPriceInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .join(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id, isouter=True)
        .where(KokCart.kok_cart_id.in_(selected_cart_ids))
        .where(KokCart.user_id == user_id)
    )

    results = (await db.execute(stmt)).all()

    if not results:
        raise ValueError("선택된 상품을 찾을 수 없습니다.")

    # 각 상품에 대해 KokOrder 생성
    kok_orders = []
    total_amount = 0

    for cart, product, price in results:
        if not price:
            continue
        
        # 프론트엔드에서 전송한 수량 찾기
        frontend_quantity = None
        for item in selected_items:
            if item["cart_id"] == cart.kok_cart_id:
                frontend_quantity = item["quantity"]
                break
        
        if frontend_quantity is None:
            continue
            
        kok_order = KokOrder(
            order_id=main_order.order_id,
            kok_price_id=price.kok_price_id,
            kok_product_id=product.kok_product_id,
            quantity=frontend_quantity  # 프론트엔드에서 전송한 수량 사용
        )
        
        db.add(kok_order)
        kok_orders.append(kok_order)
        
        # 총 금액 계산
        discounted_price = product.kok_product_price
        if price.kok_discount_rate and price.kok_discount_rate > 0:
            discounted_price = int(product.kok_product_price * (1 - price.kok_discount_rate / 100))
        
        item_total = discounted_price * frontend_quantity  # 프론트엔드 수량 사용
        total_amount += item_total
    
    # 주문 총 금액 업데이트
    main_order.total_amount = total_amount
    await db.commit()
    
    # 장바구니에서 선택된 상품들 삭제
    cart_items_to_delete = (await db.execute(
        select(KokCart).where(KokCart.kok_cart_id.in_(selected_cart_ids))
    )).scalars().all()
    
    for cart_item in cart_items_to_delete:
        await db.delete(cart_item)
    
    await db.commit()
    
    return {
        "order_id": main_order.order_id,
        "total_amount": total_amount,
        "order_count": len(kok_orders),
        "message": f"{len(kok_orders)}개의 상품이 주문되었습니다."
    }

async def get_ingredients_from_selected_cart_items(
    db: AsyncSession,
    user_id: int,
    selected_cart_ids: List[int]
) -> List[str]:
    """
    선택된 장바구니 상품들의 재료명 추출 (레시피 추천용)
    """
    if not selected_cart_ids:
        return []
    
    # 선택된 장바구니 항목들과 상품 정보 조회
    stmt = (
        select(KokCart, KokProductInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokCart.kok_cart_id.in_(selected_cart_ids))
        .where(KokCart.user_id == user_id)
    )
    
    results = (await db.execute(stmt)).all()
    
    if not results:
        return []
    
    # 상품명에서 재료명 추출 (간단한 키워드 매칭)
    ingredients = []
    ingredient_keywords = [
        "쌀", "밥", "김치", "된장", "고추장", "간장", "식용유", "참기름", "들기름",
        "소고기", "돼지고기", "닭고기", "양고기", "오리고기", "계란", "달걀",
        "양파", "마늘", "대파", "쪽파", "당근", "감자", "고구마", "애호박", "오이",
        "상추", "깻잎", "시금치", "부추", "미나리", "고사리", "콩나물", "숙주나물",
        "버섯", "표고버섯", "느타리버섯", "팽이버섯", "양송이버섯",
        "고등어", "삼치", "갈치", "조기", "굴", "새우", "오징어", "문어", "낙지",
        "두부", "순두부", "콩", "팥", "녹두", "깨", "들깨",
        "사과", "배", "복숭아", "포도", "딸기", "바나나", "오렌지", "레몬", "라임",
        "고추", "피망", "파프리카", "토마토", "가지", "무", "배추", "양배추", "브로콜리",
        "우유", "치즈", "요거트", "버터", "생크림", "휘핑크림",
        "밀가루", "전분", "빵가루", "빵", "토스트", "샌드위치",
        "설탕", "소금", "후추", "고춧가루", "카레가루", "카레", "커리",
        "물", "물엿", "올리고당", "꿀", "잼", "쨈", "잼", "쨈"
    ]
    
    for cart, product in results:
        product_name = product.kok_product_name.lower()
        
        # 키워드 매칭으로 재료명 추출
        for keyword in ingredient_keywords:
            if keyword in product_name:
                if keyword not in ingredients:
                    ingredients.append(keyword)
                break
        
        # 상품명이 재료명과 유사한 경우 직접 추가
        if len(product_name) <= 10 and not any(keyword in product_name for keyword in ingredients):
            ingredients.append(product_name)
    
    return ingredients
