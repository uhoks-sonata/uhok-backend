from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.kok.models.interaction_model import KokLikes
from services.kok.models.product_model import (
    KokDetailInfo,
    KokImageInfo,
    KokPriceInfo,
    KokProductInfo,
    KokReviewExample,
)
from services.kok.schemas.product_schema import (
    KokDetailInfoItem,
    KokProductDetails,
    KokProductDetailsResponse,
    KokProductInfoResponse,
    KokProductTabsResponse,
    KokReviewDetail,
    KokReviewResponse,
    KokReviewStats,
)

from .shared import get_latest_kok_price_id, logger

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

