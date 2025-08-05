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
    KokCart,
    KokPurchase
)

from services.order.models.order_model import KokOrders

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
# 검색 이력 관련 함수
# -----------------------------

async def get_kok_search_history(
        db: AsyncSession,
        user_id: int
) -> List[dict]:
    """
    사용자의 검색 이력을 조회
    """
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.kok_user_id == user_id)
        .order_by(KokSearchHistory.kok_searched_at.desc())
        .limit(20)
    )
    history = (await db.execute(stmt)).scalars().all()
    return [h.__dict__ for h in history]

async def add_kok_search_history(
        db: AsyncSession,
        user_id: int,
        keyword: str
) -> dict:
    """
    새로운 검색 이력을 등록
    """
    from datetime import datetime
    searched_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    new_history = KokSearchHistory(
        kok_user_id=user_id,
        kok_keyword=keyword,
        kok_searched_at=searched_at
    )
    db.add(new_history)
    await db.commit()
    await db.refresh(new_history)
    return new_history.__dict__

async def delete_kok_search_history(
        db: AsyncSession,
        user_id: int,
        keyword: str
) -> bool:
    """
    특정 키워드의 검색 이력을 삭제
    """
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.kok_user_id == user_id)
        .where(KokSearchHistory.kok_keyword == keyword)
    )
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()
    
    if history:
        await db.delete(history)
        await db.commit()
        return True
    return False

# -----------------------------
# 찜 관련 함수
# -----------------------------

async def toggle_kok_likes(
        db: AsyncSession,
        user_id: int,
        product_id: int
) -> dict:
    """
    찜 토글 (찜하기/취소하기)
    """
    stmt = (
        select(KokLikes)
        .where(KokLikes.kok_user_id == user_id)
        .where(KokLikes.kok_product_id == product_id)
    )
    result = await db.execute(stmt)
    existing_like = result.scalar_one_or_none()
    
    if existing_like:
        # 이미 찜한 경우 취소
        await db.delete(existing_like)
        await db.commit()
        return {"liked": False, "message": "찜이 취소되었습니다."}
    else:
        # 찜하지 않은 경우 찜하기
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        new_like = KokLikes(
            kok_user_id=user_id,
            kok_product_id=product_id,
            kok_created_at=created_at
        )
        db.add(new_like)
        await db.commit()
        return {"liked": True, "message": "상품을 찜했습니다."}

async def get_kok_liked_products(
        db: AsyncSession,
        user_id: int
) -> List[dict]:
    """
    사용자가 찜한 상품 목록 조회
    """
    stmt = (
        select(KokLikes, KokProductInfo)
        .join(KokProductInfo, KokLikes.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokLikes.kok_user_id == user_id)
        .order_by(KokLikes.kok_created_at.desc())
    )
    results = (await db.execute(stmt)).all()
    
    liked_products = []
    for like, product in results:
        liked_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_thumbnail_url": product.kok_thumbnail  # thumbnail_url은 thumbnail과 동일
        })
    
    return liked_products

# -----------------------------
# 장바구니 관련 함수
# -----------------------------

async def toggle_kok_cart(
        db: AsyncSession,
        user_id: int,
        product_id: int
) -> dict:
    """
    장바구니 토글 (추가/제거)
    """
    stmt = (
        select(KokCart)
        .where(KokCart.kok_user_id == user_id)
        .where(KokCart.kok_product_id == product_id)
    )
    result = await db.execute(stmt)
    existing_cart = result.scalar_one_or_none()
    
    if existing_cart:
        # 이미 장바구니에 있는 경우 제거
        await db.delete(existing_cart)
        await db.commit()
        return {"in_cart": False, "message": "장바구니에서 제거되었습니다."}
    else:
        # 장바구니에 없는 경우 추가
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        new_cart = KokCart(
            kok_user_id=user_id,
            kok_product_id=product_id,
            kok_quantity=1,
            kok_created_at=created_at
        )
        db.add(new_cart)
        await db.commit()
        return {"in_cart": True, "message": "장바구니에 추가되었습니다."}

async def get_kok_cart_items(
        db: AsyncSession,
        user_id: int
) -> List[dict]:
    """
    사용자의 장바구니 상품 목록 조회
    """
    stmt = (
        select(KokCart, KokProductInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokCart.kok_user_id == user_id)
        .order_by(KokCart.kok_created_at.desc())
    )
    results = (await db.execute(stmt)).all()
    
    cart_items = []
    for cart, product in results:
        cart_items.append({
            "kok_product_id": product.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_product_price": product.kok_product_price,
            "kok_quantity": cart.kok_quantity
        })
    
    return cart_items

# -----------------------------
# 메인화면 상품 리스트 함수
# -----------------------------

async def get_kok_discounted_products(
        db: AsyncSession
) -> List[dict]:
    """
    할인 특가 상품 목록 조회 (할인율 높은 순으로 정렬)
    """
    stmt = (
        select(KokProductInfo)
        .where(KokProductInfo.kok_discount_rate > 0)
        .order_by(KokProductInfo.kok_discount_rate.desc())
        .limit(10)
    )
    products = (await db.execute(stmt)).scalars().all()
    
    discounted_products = []
    for product in products:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        if product.kok_discount_rate and product.kok_discount_rate > 0:
            discounted_price = int(product.kok_product_price * (1 - product.kok_discount_rate / 100))
        
        discounted_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": product.kok_discount_rate,
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
    stmt = (
        select(KokProductInfo)
        .where(KokProductInfo.kok_review_cnt > 0)
        .order_by(KokProductInfo.kok_review_cnt.desc())
        .limit(20)
    )
    products = (await db.execute(stmt)).scalars().all()
    
    top_selling_products = []
    for product in products:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        if product.kok_discount_rate and product.kok_discount_rate > 0:
            discounted_price = int(product.kok_product_price * (1 - product.kok_discount_rate / 100))
        
        top_selling_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": product.kok_discount_rate,
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
    
    purchased_products_stmt = (
        select(KokPurchase.kok_product_id)
        .where(KokPurchase.kok_user_id == user_id)
        .where(KokPurchase.kok_purchased_at >= thirty_days_ago)
    )
    purchased_products = (await db.execute(purchased_products_stmt)).scalars().all()
    purchased_product_ids = [p.kok_product_id for p in purchased_products]
    
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
        select(KokOrders, KokPriceInfo, KokProductInfo)
        .join(KokPriceInfo, KokOrders.price_id == KokPriceInfo.kok_price_id)
        .join(KokProductInfo, KokPriceInfo.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokOrders.user_id == user_id)
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
        select(KokProductInfo)
        .where(KokProductInfo.kok_store_name.in_(store_names))
        .where(KokProductInfo.kok_review_cnt > 0)
        .order_by(KokProductInfo.kok_review_cnt.desc())
        .limit(10)
    )
    store_products = (await db.execute(store_best_stmt)).scalars().all()
    
    store_best_products = []
    for product in store_products:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        if product.kok_discount_rate and product.kok_discount_rate > 0:
            discounted_price = int(product.kok_product_price * (1 - product.kok_discount_rate / 100))
        
        store_best_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": product.kok_discount_rate,
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

async def search_kok_products(
        db: AsyncSession,
        keyword: str,
        page: int = 1,
        size: int = 10
) -> List[dict]:
    """
    키워드로 제품 검색 (필요한 필드만 반환)
    """
    offset = (page - 1) * size
    stmt = (
        select(KokProductInfo)
        .where(
            KokProductInfo.kok_product_name.contains(keyword) |
            KokProductInfo.kok_store_name.contains(keyword) |
            KokProductInfo.kok_description.contains(keyword)
        )
        .order_by(KokProductInfo.kok_review_score.desc())
        .offset(offset)
        .limit(size)
    )
    products = (await db.execute(stmt)).scalars().all()
    
    search_products = []
    for product in products:
        # 할인 적용 가격 계산
        discounted_price = product.kok_product_price
        if product.kok_discount_rate and product.kok_discount_rate > 0:
            discounted_price = int(product.kok_product_price * (1 - product.kok_discount_rate / 100))
        
        search_products.append({
            "kok_product_id": product.kok_product_id,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_discount_rate": product.kok_discount_rate,
            "kok_discounted_price": discounted_price,
            "kok_product_name": product.kok_product_name,
            "kok_store_name": product.kok_store_name,
        })
    
    return search_products


async def add_kok_purchase(
        db: AsyncSession,
        user_id: int,
        product_id: int,
        quantity: int = 1,
        purchase_price: Optional[int] = None
) -> dict:
    """
    구매 이력 추가
    """
    from datetime import datetime
    
    # 구매 가격이 없으면 제품 가격으로 설정
    if purchase_price is None:
        product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == product_id)
        product = (await db.execute(product_stmt)).scalar_one_or_none()
        if product:
            purchase_price = product.kok_product_price
    
    purchased_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    new_purchase = KokPurchase(
        kok_user_id=user_id,
        kok_product_id=product_id,
        kok_quantity=quantity,
        kok_purchase_price=purchase_price,
        kok_purchased_at=purchased_at
    )
    
    db.add(new_purchase)
    await db.commit()
    await db.refresh(new_purchase)
    
    return new_purchase.__dict__


async def get_kok_purchase_history(
        db: AsyncSession,
        user_id: int,
        limit: int = 10
) -> List[dict]:
    """
    사용자의 구매 이력 조회
    """
    stmt = (
        select(KokPurchase, KokProductInfo)
        .join(KokProductInfo, KokPurchase.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokPurchase.kok_user_id == user_id)
        .order_by(KokPurchase.kok_purchased_at.desc())
        .limit(limit)
    )
    
    results = (await db.execute(stmt)).all()
    
    purchase_history = []
    for purchase, product in results:
        purchase_history.append({
            "kok_purchase_id": purchase.kok_purchase_id,
            "kok_product_id": purchase.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "kok_thumbnail": product.kok_thumbnail,
            "kok_quantity": purchase.kok_quantity,
            "kok_purchase_price": purchase.kok_purchase_price,
            "kok_purchased_at": purchase.kok_purchased_at
        })
    
    return purchase_history

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
        select(KokProductInfo)
        .where(KokProductInfo.kok_product_name.ilike(f"%{ingredient}%"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    return [
        {
            "kok_product_id": p.kok_product_id,
            "kok_product_name": p.kok_product_name,
            "kok_thumbnail": p.kok_thumbnail,
            "kok_store_name": p.kok_store_name,
            "kok_product_price": p.kok_product_price,
            "kok_discount_rate": p.kok_discount_rate,
            "kok_discounted_price": (
                p.price_infos[0].kok_discounted_price
                if p.price_infos and p.price_infos[0].kok_discounted_price
                else p.kok_product_price
            ),
            "kok_review_score": p.kok_review_score,
            "kok_review_cnt": p.kok_review_cnt,
            # 필요시 model에 정의된 추가 필드도 동일하게 추출
        }
        for p in products
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
