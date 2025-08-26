"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
from __future__ import annotations
from typing import Dict, Any, List
import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession 
from services.order.models.order_model import (
    Order, KokOrder, HomeShoppingOrder
)
from services.kok.models.kok_model import KokProductInfo, KokImageInfo
from services.homeshopping.models.homeshopping_model import HomeshoppingList, HomeshoppingImgUrl
from services.recipe.models.recipe_model import Recipe

from services.order.crud.kok_order_crud import update_kok_order_status, calculate_kok_order_price
from services.order.crud.hs_order_crud import calculate_homeshopping_order_price, update_hs_order_status
from services.recipe.crud.recipe_crud import fetch_recipe_ingredients_status

from common.logger import get_logger
logger = get_logger("order_crud")


async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order).where(Order.order_id == order_id)
    )
    order = result.scalars().first()
    
    if not order:
        return None
    
    # 콕 주문 정보 조회
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order.order_id)
    )
    kok_orders = kok_result.scalars().all()
    
    # 홈쇼핑 주문 정보 조회
    homeshopping_result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
    )
    homeshopping_orders = homeshopping_result.scalars().all()
    
    # 딕셔너리 형태로 반환
    return {
        "order_id": order.order_id,
        "user_id": order.user_id,
        "order_time": order.order_time,
        "cancel_time": order.cancel_time,
        "kok_orders": kok_orders,
        "homeshopping_orders": homeshopping_orders
    }


async def get_user_orders(db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0) -> list:
    """
    사용자별 주문 목록 조회 (공통 정보 + 서비스별 상세 + 상품 이미지)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.order_time.desc())
        .offset(offset)
        .limit(limit)
    )
    orders = result.scalars().all()
    
    order_list = []
    for order in orders:
        # 콕 주문 정보 조회 (상품 이미지 포함)
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_orders = kok_result.scalars().all()
        
        # 콕 주문에 상품 이미지 정보 추가
        for kok_order in kok_orders:
            try:         
                # 상품 기본 정보 조회
                product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_order.kok_product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product:
                    # 썸네일 이미지가 있으면 사용
                    if product.kok_thumbnail:
                        kok_order.product_image = product.kok_thumbnail
                    else:
                        # 썸네일이 없으면 첫 번째 이미지 사용
                        img_stmt = select(KokImageInfo).where(KokImageInfo.kok_product_id == kok_order.kok_product_id).limit(1)
                        img_result = await db.execute(img_stmt)
                        img = img_result.scalar_one_or_none()
                        kok_order.product_image = img.kok_img_url if img else None
                        
                    # 상품명도 추가
                    kok_order.product_name = product.kok_product_name
                else:
                    kok_order.product_image = None
                    kok_order.product_name = None
                
                # 레시피 정보 조회 (recipe_id가 있는 경우)
                if kok_order.recipe_id:
                    try:                        
                        recipe_stmt = select(Recipe).where(Recipe.recipe_id == kok_order.recipe_id)
                        recipe_result = await db.execute(recipe_stmt)
                        recipe = recipe_result.scalar_one_or_none()
                        
                        if recipe:
                            kok_order.recipe_title = recipe.recipe_title
                            kok_order.recipe_description = recipe.recipe_description
                            kok_order.recipe_rating = recipe.rating if hasattr(recipe, 'rating') else 0.0
                            kok_order.recipe_scrap_count = recipe.scrap_count if hasattr(recipe, 'scrap_count') else 0
                            
                            # 재료 정보 조회
                            try:
                                ingredients_status = await fetch_recipe_ingredients_status(db, kok_order.recipe_id, user_id)
                                kok_order.ingredients_owned = ingredients_status.get('owned_count', 0)
                                kok_order.total_ingredients = ingredients_status.get('total_count', 0)
                            except Exception as e:
                                logger.warning(f"레시피 재료 정보 조회 실패: recipe_id={kok_order.recipe_id}, error={str(e)}")
                                kok_order.ingredients_owned = 0
                                kok_order.total_ingredients = 0
                        else:
                            kok_order.recipe_title = None
                            kok_order.recipe_description = None
                            kok_order.recipe_rating = 0.0
                            kok_order.recipe_scrap_count = 0
                            kok_order.ingredients_owned = 0
                            kok_order.total_ingredients = 0
                            
                    except Exception as e:
                        logger.warning(f"레시피 정보 조회 실패: recipe_id={kok_order.recipe_id}, error={str(e)}")
                        kok_order.recipe_title = None
                        kok_order.recipe_description = None
                        kok_order.recipe_rating = 0.0
                        kok_order.recipe_scrap_count = 0
                        kok_order.ingredients_owned = 0
                        kok_order.total_ingredients = 0
                else:
                    # 레시피가 없는 경우
                    kok_order.recipe_title = None
                    kok_order.recipe_description = None
                    kok_order.recipe_rating = 0.0
                    kok_order.recipe_scrap_count = 0
                    kok_order.ingredients_owned = 0
                    kok_order.total_ingredients = 0
                    
            except Exception as e:
                logger.warning(f"콕 상품 이미지 조회 실패: kok_product_id={kok_order.kok_product_id}, error={str(e)}")
                kok_order.product_image = None
                kok_order.product_name = None
                kok_order.recipe_title = None
                kok_order.recipe_description = None
                kok_order.recipe_rating = 0.0
                kok_order.recipe_scrap_count = 0
                kok_order.ingredients_owned = 0
                kok_order.total_ingredients = 0
        
        # 홈쇼핑 주문 정보 조회 (상품 이미지 포함)
        homeshopping_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
        )
        homeshopping_orders = homeshopping_result.scalars().all()
        
        # 홈쇼핑 주문에 상품 이미지 정보 추가
        for hs_order in homeshopping_orders:
            try:
                # 상품 기본 정보 조회
                product_stmt = select(HomeshoppingList).where(HomeshoppingList.product_id == hs_order.product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product:
                    # 썸네일 이미지가 있으면 사용
                    if product.thumb_img_url:
                        hs_order.product_image = product.thumb_img_url
                    else:
                        # 썸네일이 없으면 첫 번째 이미지 사용
                        img_stmt = select(HomeshoppingImgUrl).where(HomeshoppingImgUrl.product_id == hs_order.product_id).order_by(HomeshoppingImgUrl.sort_order).limit(1)
                        img_result = await db.execute(img_stmt)
                        img = img_result.scalar_one_or_none()
                        hs_order.product_image = img.img_url if img else None
                        
                    # 상품명도 추가
                    hs_order.product_name = product.product_name
                else:
                    hs_order.product_image = None
                    hs_order.product_name = None
                    
            except Exception as e:
                logger.warning(f"홈쇼핑 상품 이미지 조회 실패: product_id={hs_order.product_id}, error={str(e)}")
                hs_order.product_image = None
                hs_order.product_name = None
        
        order_list.append({
            "order_id": order.order_id,
            "user_id": order.user_id,
            "order_time": order.order_time,
            "cancel_time": order.cancel_time,
            "kok_orders": kok_orders,
            "homeshopping_orders": homeshopping_orders
        })
    
    return order_list


async def calculate_order_total_price(db: AsyncSession, order_id: int) -> int:
    """
    주문 ID로 총 주문 금액 계산 (콕 주문 + 홈쇼핑 주문)
    각 주문 타입별로 이미 계산된 order_price 사용
    """
    logger.info(f"주문 총액 계산 시작: order_id={order_id}")
    total_price = 0
    
    # 콕 주문 총액 계산
    logger.info(f"콕 주문 총액 계산 시작: order_id={order_id}")
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order_id)
    )
    kok_orders = kok_result.scalars().all()
    logger.info(f"콕 주문 조회 결과: order_id={order_id}, kok_count={len(kok_orders)}")
    
    for kok_order in kok_orders:
        if hasattr(kok_order, 'order_price') and kok_order.order_price:
            logger.info(f"콕 주문 기존 가격 사용: kok_order_id={kok_order.kok_order_id}, order_price={kok_order.order_price}")
            total_price += kok_order.order_price
        else:
            # order_price가 없는 경우 계산 함수 사용
            logger.info(f"콕 주문 가격 계산 필요: kok_order_id={kok_order.kok_order_id}, kok_price_id={kok_order.kok_price_id}")
            try:
                price_info = await calculate_kok_order_price(
                    db, 
                    kok_order.kok_price_id, 
                    kok_order.kok_product_id, 
                    kok_order.quantity
                )
                total_price += price_info["order_price"]
                logger.info(f"콕 주문 가격 계산 완료: kok_order_id={kok_order.kok_order_id}, calculated_price={price_info['order_price']}")
            except Exception as e:
                logger.warning(f"콕 주문 금액 계산 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                # 기본값 사용
                fallback_price = getattr(kok_order, 'dc_price', 0) * getattr(kok_order, 'quantity', 1)
                total_price += fallback_price
                logger.info(f"콕 주문 기본값 사용: kok_order_id={kok_order.kok_order_id}, fallback_price={fallback_price}")
    
    # 홈쇼핑 주문 총액 계산
    logger.info(f"홈쇼핑 주문 총액 계산 시작: order_id={order_id}")
    homeshopping_result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order_id)
    )
    homeshopping_orders = homeshopping_result.scalars().all()
    logger.info(f"홈쇼핑 주문 조회 결과: order_id={order_id}, hs_count={len(homeshopping_orders)}")
    
    for hs_order in homeshopping_orders:
        if hasattr(hs_order, 'order_price') and hs_order.order_price:
            logger.info(f"홈쇼핑 주문 기존 가격 사용: hs_order_id={hs_order.homeshopping_order_id}, order_price={hs_order.order_price}")
            total_price += hs_order.order_price
        else:
            # order_price가 없는 경우 계산 함수 사용
            logger.info(f"홈쇼핑 주문 가격 계산 필요: hs_order_id={hs_order.homeshopping_order_id}, product_id={hs_order.product_id}")
            try:
                price_info = await calculate_homeshopping_order_price(
                    db, 
                    hs_order.product_id, 
                    hs_order.quantity
                )
                total_price += price_info["order_price"]
                logger.info(f"홈쇼핑 주문 가격 계산 완료: hs_order_id={hs_order.homeshopping_order_id}, calculated_price={price_info['order_price']}")
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 금액 계산 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                # 기본값 사용
                fallback_price = getattr(hs_order, 'dc_price', 0) * getattr(hs_order, 'quantity', 1)
                total_price += fallback_price
                logger.info(f"홈쇼핑 주문 기본값 사용: hs_order_id={hs_order.homeshopping_order_id}, fallback_price={fallback_price}")
    
    logger.info(f"주문 총액 계산 완료: order_id={order_id}, total_price={total_price}")
    return total_price


async def _post_json(url: str, json: Dict[str, Any], timeout: float = 20.0) -> httpx.Response:
    """
    비동기 HTTP POST 유틸
    - httpx.AsyncClient를 context manager로 생성하여 커넥션 누수 방지
    - timeout: 연결/읽기 통합 타임아웃(초)
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=json, headers={"Content-Type": "application/json"})


async def _get_json(url: str, timeout: float = 15.0) -> httpx.Response:
    """
    비동기 HTTP GET 유틸
    - httpx.AsyncClient 사용
    - timeout: 연결/읽기 통합 타임아웃(초)
    """
    logger.info(f"HTTP GET 요청 시작: url={url}, timeout={timeout}초")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"httpx.AsyncClient 생성 완료, GET 요청 전송: {url}")
            response = await client.get(url)
            logger.info(f"HTTP GET 응답 수신: url={url}, status_code={response.status_code}")
            return response
    except Exception as e:
        logger.error(f"HTTP GET 요청 실패: url={url}, error={str(e)}, error_type={type(e).__name__}")
        raise


async def _mark_all_children_paid(
    db: AsyncSession,
    *,
    kok_orders: List[Any],
    hs_orders: List[Any],
    user_id: int,
) -> None:
    """
    하위 주문(콕/홈쇼핑)을 PAYMENT_COMPLETED로 일괄 갱신
    - 기존 트랜잭션 사용 (새로운 트랜잭션 시작하지 않음)
    - 실패 시 상위에서 롤백 처리
    """
    logger.info(f"하위 주문 상태 갱신 시작: kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 콕 주문 상태 갱신
    for k in kok_orders:
        try:
            await update_kok_order_status(
                db=db,
                kok_order_id=k.kok_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
            logger.info(f"콕 주문 상태 갱신 완료: kok_order_id={k.kok_order_id}")
        except Exception as e:
            logger.error(f"콕 주문 상태 갱신 실패: kok_order_id={k.kok_order_id}, error={str(e)}")
            raise
    
    # 홈쇼핑 주문 상태 갱신
    for h in hs_orders:
        try:
            await update_hs_order_status(
                db=db,
                homeshopping_order_id=h.homeshopping_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
            logger.info(f"홈쇼핑 주문 상태 갱신 완료: hs_order_id={h.homeshopping_order_id}")
        except Exception as e:
            logger.error(f"홈쇼핑 주문 상태 갱신 실패: hs_order_id={h.homeshopping_order_id}, error={str(e)}")
            raise
    
    logger.info(f"모든 하위 주문 상태 갱신 완료")


async def _ensure_order_access(db: AsyncSession, order_id: int, user_id: int) -> Dict[str, Any]:
    """
    주문 존재/권한 확인 유틸
    - 해당 order_id가 존재하고, 소유자가 user_id인지 확인
    - dict(order) 반환, 없거나 권한 없으면 404
    """
    logger.info(f"주문 접근 권한 확인: order_id={order_id}, user_id={user_id}")
    
    order_data = await get_order_by_id(db, order_id)
    logger.info(f"주문 데이터 조회 결과: order_id={order_id}, order_data={order_data is not None}")
    
    if not order_data:
        logger.error(f"주문을 찾을 수 없음: order_id={order_id}")
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    
    if order_data["user_id"] != user_id:
        logger.error(f"주문 접근 권한 없음: order_id={order_id}, order_user_id={order_data['user_id']}, request_user_id={user_id}")
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    
    logger.info(f"주문 접근 권한 확인 완료: order_id={order_id}, user_id={user_id}")
    return order_data

