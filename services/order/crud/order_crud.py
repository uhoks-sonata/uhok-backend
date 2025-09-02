"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
CRUD 계층: 모든 DB 트랜잭션 처리 담당
"""
from __future__ import annotations
import httpx
import asyncio
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import Dict, Any, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession 

from common.logger import get_logger

from services.order.models.order_model import (
    Order, KokOrder, KokOrderStatusHistory, 
    HomeShoppingOrder, HomeShoppingOrderStatusHistory, 
    StatusMaster
)
from services.kok.models.kok_model import KokProductInfo, KokImageInfo
from services.homeshopping.models.homeshopping_model import HomeshoppingList, HomeshoppingImgUrl
from services.recipe.models.recipe_model import Recipe, Material

from services.order.crud.kok_order_crud import update_kok_order_status, calculate_kok_order_price
from services.order.crud.hs_order_crud import calculate_homeshopping_order_price, update_hs_order_status
from services.recipe.crud.recipe_crud import fetch_recipe_ingredients_status

logger = get_logger("order_crud")


async def get_delivery_info(db: AsyncSession, order_type: str, order_id: int) -> tuple[str, str]:
    """
    주문의 배송 상태와 배송완료 날짜를 조회하는 헬퍼 함수
    
    Args:
        db: 데이터베이스 세션
        order_type: 주문 타입 ("kok" 또는 "homeshopping")
        order_id: 주문 ID (kok_order_id 또는 homeshopping_order_id)
    
    Returns:
        tuple: (delivery_status, delivery_date)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 배송완료 상태인 경우 한국어 형식으로 날짜 포맷팅
    """
    try:
        if order_type == "kok":
            # 콕 주문의 현재 상태 조회
            result = await db.execute(
                select(KokOrderStatusHistory, StatusMaster)
                .join(StatusMaster, KokOrderStatusHistory.status_id == StatusMaster.status_id)
                .where(KokOrderStatusHistory.kok_order_id == order_id)
                .order_by(desc(KokOrderStatusHistory.changed_at))
                .limit(1)
            )
            status_history = result.first()
        else:
            # 홈쇼핑 주문의 현재 상태 조회
            result = await db.execute(
                select(HomeShoppingOrderStatusHistory, StatusMaster)
                .join(StatusMaster, HomeShoppingOrderStatusHistory.status_id == StatusMaster.status_id)
                .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == order_id)
                .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
                .limit(1)
            )
            status_history = result.first()
        
        if not status_history or len(status_history) < 2:
            return "주문접수", "배송 정보 없음"
        
        # status_history[0]은 상태 이력, status_history[1]은 상태 마스터
        status_record = status_history[0]
        status_master = status_history[1]
        
        if not status_record or not status_master:
            return "주문접수", "배송 정보 없음"
        
        current_status = status_master.status_name
        changed_at = status_record.changed_at
        
        # 배송완료 상태인 경우 배송완료 날짜 설정
        if current_status == "배송완료":
            # 배송완료 날짜를 한국어 형식으로 포맷팅
            month = changed_at.month
            day = changed_at.day
            weekday = ["월", "화", "수", "목", "금", "토", "일"][changed_at.weekday()]
            delivery_date = f"{month}/{day}({weekday}) 도착"
        else:
            # 배송완료가 아닌 경우 상태에 따른 메시지
            delivery_date = "배송 정보 없음"
        
        return current_status, delivery_date
        
    except Exception as e:
        logger.warning(f"배송 정보 조회 실패: order_type={order_type}, order_id={order_id}, error={str(e)}")
        return "상태 조회 실패", "배송 정보 없음"


async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    
    Args:
        db: 데이터베이스 세션
        order_id: 조회할 주문 ID
    
    Returns:
        dict: 주문 정보 (order_id, user_id, order_time, cancel_time, kok_orders, homeshopping_orders)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 콕 주문과 홈쇼핑 주문 정보를 모두 포함하여 반환
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
    
    Args:
        db: 데이터베이스 세션
        user_id: 조회할 사용자 ID
        limit: 조회할 주문 개수 (기본값: 20)
        offset: 건너뛸 주문 개수 (기본값: 0)
    
    Returns:
        list: 사용자의 주문 목록 (각 주문에 상품 이미지, 레시피 정보 포함)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 콕 주문: 상품 이미지, 레시피 정보, 재료 보유 현황 포함
        - 홈쇼핑 주문: 상품 이미지 포함
        - 최신 주문순으로 정렬
        - 최적화: N+1 쿼리 문제 해결을 위해 JOIN과 배치 쿼리 사용
    """
    # 1. 주문 기본 정보와 콕 주문 정보를 JOIN으로 한 번에 조회
    kok_orders_stmt = (
        select(
            Order.order_id, Order.user_id, Order.order_time, Order.cancel_time,
            KokOrder.kok_order_id, KokOrder.kok_product_id, KokOrder.quantity,
            KokOrder.order_price, KokOrder.recipe_id, KokOrder.kok_price_id,
            KokProductInfo.kok_product_name, KokProductInfo.kok_thumbnail,
            Recipe.recipe_title, Recipe.cooking_introduction, Recipe.scrap_count
        )
        .outerjoin(KokOrder, Order.order_id == KokOrder.order_id)
        .outerjoin(KokProductInfo, KokOrder.kok_product_id == KokProductInfo.kok_product_id)
        .outerjoin(Recipe, KokOrder.recipe_id == Recipe.recipe_id)
        .where(Order.user_id == user_id)
        .order_by(Order.order_time.desc())
        .offset(offset)
        .limit(limit)
    )
    
    # 2. 주문 기본 정보와 홈쇼핑 주문 정보를 JOIN으로 한 번에 조회
    hs_orders_stmt = (
        select(
            Order.order_id, Order.user_id, Order.order_time, Order.cancel_time,
            HomeShoppingOrder.homeshopping_order_id, HomeShoppingOrder.product_id,
            HomeShoppingOrder.quantity, HomeShoppingOrder.order_price, HomeShoppingOrder.dc_price,
            HomeshoppingList.product_name, HomeshoppingList.thumb_img_url
        )
        .outerjoin(HomeShoppingOrder, Order.order_id == HomeShoppingOrder.order_id)
        .outerjoin(HomeshoppingList, HomeShoppingOrder.product_id == HomeshoppingList.product_id)
        .where(Order.user_id == user_id)
        .order_by(Order.order_time.desc())
        .offset(offset)
        .limit(limit)
    )
    
    # 3. 두 쿼리를 병렬로 실행 (SQLAlchemy 2.0에서는 제한적)
    try:
        kok_result, hs_result = await asyncio.gather(
            db.execute(kok_orders_stmt),
            db.execute(hs_orders_stmt)
        )
    except Exception as e:
        # 병렬 실행 실패 시 순차 실행으로 폴백
        logger.warning(f"병렬 쿼리 실행 실패, 순차 실행으로 전환: {e}")
        kok_result = await db.execute(kok_orders_stmt)
        hs_result = await db.execute(hs_orders_stmt)
    
    kok_orders_data = kok_result.all()
    hs_orders_data = hs_result.all()
    
    # 4. 레시피가 있는 콕 주문들의 recipe_id 수집 (재료 상태 배치 조회용)
    recipe_ids = list(set(
        row.recipe_id for row in kok_orders_data 
        if row.recipe_id is not None
    ))
    
    # 5. 재료 상태를 배치로 조회 (가장 비용이 큰 부분)
    ingredients_cache = {}
    if recipe_ids:
        try:
            ingredients_cache = await _batch_fetch_recipe_ingredients_status(db, recipe_ids, user_id)
        except Exception as e:
            logger.warning(f"재료 상태 배치 조회 실패: {str(e)}")
    
    # 6. 콕 주문 이미지 정보를 배치로 조회 (썸네일이 없는 경우)
    kok_product_ids_without_thumbnail = list(set(
        row.kok_product_id for row in kok_orders_data 
        if row.kok_thumbnail is None and row.kok_product_id is not None
    ))
    
    images_cache = {}
    if kok_product_ids_without_thumbnail:
        try:
            images_cache = await _batch_fetch_kok_images(db, kok_product_ids_without_thumbnail)
        except Exception as e:
            logger.warning(f"콕 상품 이미지 배치 조회 실패: {str(e)}")
    
    # 7. 홈쇼핑 주문 이미지 정보를 배치로 조회 (썸네일이 없는 경우)
    hs_product_ids_without_thumbnail = list(set(
        row.product_id for row in hs_orders_data 
        if row.thumb_img_url is None and row.product_id is not None
    ))
    
    hs_images_cache = {}
    if hs_product_ids_without_thumbnail:
        try:
            hs_images_cache = await _batch_fetch_hs_images(db, hs_product_ids_without_thumbnail)
        except Exception as e:
            logger.warning(f"홈쇼핑 상품 이미지 배치 조회 실패: {str(e)}")
    
    # 8. 결과 데이터 구조화 (기존 형식과 동일하게 유지)
    order_dict = {}
    
    # 콕 주문 데이터 처리
    for row in kok_orders_data:
        if row.order_id not in order_dict:
            order_dict[row.order_id] = {
                "order_id": row.order_id,
                "user_id": row.user_id,
                "order_time": row.order_time,
                "cancel_time": row.cancel_time,
                "kok_orders": [],
                "homeshopping_orders": []
            }
        
        if row.kok_order_id:  # 콕 주문이 있는 경우만
            kok_order = KokOrder()
            kok_order.kok_order_id = row.kok_order_id
            kok_order.kok_product_id = row.kok_product_id
            kok_order.quantity = row.quantity
            kok_order.order_price = row.order_price
            kok_order.recipe_id = row.recipe_id
            kok_order.kok_price_id = row.kok_price_id
            
            # 상품 정보 설정
            kok_order.product_name = row.kok_product_name
            if row.kok_thumbnail:
                kok_order.product_image = row.kok_thumbnail
            else:
                # 썸네일이 없는 경우 이미지 캐시에서 가져오기
                kok_order.product_image = images_cache.get(row.kok_product_id)
            
            # 레시피 정보 설정
            if row.recipe_id:
                kok_order.recipe_title = row.recipe_title
                kok_order.recipe_description = row.cooking_introduction
                kok_order.recipe_rating = 0.0  # Recipe 모델에 rating 필드가 없음
                kok_order.recipe_scrap_count = row.scrap_count or 0
                
                # 재료 정보 설정
                ingredients_info = ingredients_cache.get(row.recipe_id, {})
                if 'summary' in ingredients_info:
                    kok_order.ingredients_owned = ingredients_info['summary'].get('owned_count', 0)
                    kok_order.total_ingredients = ingredients_info['summary'].get('total_count', 0)
                else:
                    kok_order.ingredients_owned = 0
                    kok_order.total_ingredients = 0
            else:
                kok_order.recipe_title = None
                kok_order.recipe_description = None
                kok_order.recipe_rating = 0.0
                kok_order.recipe_scrap_count = 0
                kok_order.ingredients_owned = 0
                kok_order.total_ingredients = 0
            
            order_dict[row.order_id]["kok_orders"].append(kok_order)
    
    # 홈쇼핑 주문 데이터 처리
    for row in hs_orders_data:
        if row.order_id not in order_dict:
            order_dict[row.order_id] = {
                "order_id": row.order_id,
                "user_id": row.user_id,
                "order_time": row.order_time,
                "cancel_time": row.cancel_time,
                "kok_orders": [],
                "homeshopping_orders": []
            }
        
        if row.homeshopping_order_id:  # 홈쇼핑 주문이 있는 경우만
            hs_order = HomeShoppingOrder()
            hs_order.homeshopping_order_id = row.homeshopping_order_id
            hs_order.product_id = row.product_id
            hs_order.quantity = row.quantity
            hs_order.order_price = row.order_price
            hs_order.dc_price = row.dc_price
            
            # 상품 정보 설정
            hs_order.product_name = row.product_name
            if row.thumb_img_url:
                hs_order.product_image = row.thumb_img_url
            else:
                # 썸네일이 없는 경우 이미지 캐시에서 가져오기
                hs_order.product_image = hs_images_cache.get(row.product_id)
            
            order_dict[row.order_id]["homeshopping_orders"].append(hs_order)
    
    # 9. 최신 주문순으로 정렬하여 반환
    order_list = list(order_dict.values())
    order_list.sort(key=lambda x: x["order_time"], reverse=True)
    
    return order_list


async def _batch_fetch_recipe_ingredients_status(
    db: AsyncSession, 
    recipe_ids: List[int], 
    user_id: int
) -> Dict[int, Dict]:
    """
    여러 레시피의 재료 상태를 배치로 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        recipe_ids: 조회할 레시피 ID 목록
        user_id: 사용자 ID
    
    Returns:
        Dict[int, Dict]: recipe_id를 키로 하는 재료 상태 정보
    """
    if not recipe_ids:
        return {}
    
    # 1. 모든 레시피의 재료를 한 번에 조회
    materials_stmt = select(Material).where(Material.recipe_id.in_(recipe_ids))
    materials_result = await db.execute(materials_stmt)
    materials = materials_result.scalars().all()
    
    # 재료별로 그룹화
    recipe_materials = {}
    for material in materials:
        if material.recipe_id not in recipe_materials:
            recipe_materials[material.recipe_id] = []
        recipe_materials[material.recipe_id].append(material.material_name)
    
    # 2. 최근 7일 내 주문 정보를 한 번에 조회 (콕 + 홈쇼핑)
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    # 콕 주문 조회
    kok_orders_stmt = (
        select(
            Order.order_id, 
            Order.order_time,
            KokOrder.kok_order_id,
            KokProductInfo.kok_product_name
        )
        .join(KokOrder, Order.order_id == KokOrder.order_id)
        .join(KokProductInfo, KokOrder.kok_product_id == KokProductInfo.kok_product_id)
        .where(Order.user_id == user_id)
        .where(Order.order_time >= seven_days_ago)
        .where(Order.cancel_time.is_(None))
    )
    
    # 홈쇼핑 주문 조회
    hs_orders_stmt = (
        select(
            Order.order_id,
            Order.order_time,
            HomeShoppingOrder.homeshopping_order_id,
            HomeshoppingList.product_name
        )
        .join(HomeShoppingOrder, Order.order_id == HomeShoppingOrder.order_id)
        .join(HomeshoppingList, HomeShoppingOrder.product_id == HomeshoppingList.product_id)
        .where(Order.user_id == user_id)
        .where(Order.order_time >= seven_days_ago)
        .where(Order.cancel_time.is_(None))
    )
    
    # 병렬로 주문 정보 조회 (SQLAlchemy 2.0에서는 제한적)
    try:
        kok_result, hs_result = await asyncio.gather(
            db.execute(kok_orders_stmt),
            db.execute(hs_orders_stmt)
        )
    except Exception as e:
        # 병렬 실행 실패 시 순차 실행으로 폴백
        logger.warning(f"병렬 쿼리 실행 실패, 순차 실행으로 전환: {e}")
        kok_result = await db.execute(kok_orders_stmt)
        hs_result = await db.execute(hs_orders_stmt)
    
    kok_orders = kok_result.all()
    hs_orders = hs_result.all()
    
    # 주문한 상품명으로 보유 재료 구성
    owned_materials = []
    
    for order_id, order_time, kok_order_id, product_name in kok_orders:
        if product_name:
            owned_materials.append({
                "material_name": product_name,
                "order_date": order_time,
                "order_id": order_id,
                "order_type": "kok"
            })
    
    for order_id, order_time, homeshopping_order_id, product_name in hs_orders:
        if product_name:
            owned_materials.append({
                "material_name": product_name,
                "order_date": order_time,
                "order_id": order_id,
                "order_type": "homeshopping"
            })
    
    # 3. 장바구니 정보를 배치로 조회
    cart_materials = []
    try:
        from services.kok.crud.kok_crud import get_kok_cart_items
        from services.homeshopping.crud.homeshopping_crud import get_homeshopping_cart_items
        
        # 병렬로 장바구니 정보 조회 (SQLAlchemy 2.0에서는 제한적)
        try:
            kok_cart_items, hs_cart_items = await asyncio.gather(
                get_kok_cart_items(db, user_id),
                get_homeshopping_cart_items(db, user_id)
            )
        except Exception as e:
            # 병렬 실행 실패 시 순차 실행으로 폴백
            logger.warning(f"병렬 장바구니 조회 실패, 순차 실행으로 전환: {e}")
            kok_cart_items = await get_kok_cart_items(db, user_id)
            hs_cart_items = await get_homeshopping_cart_items(db, user_id)
        
        # 콕 장바구니 처리
        for cart_item in kok_cart_items:
            if cart_item.get("kok_product_name"):
                cart_materials.append({
                    "material_name": cart_item["kok_product_name"],
                    "cart_id": cart_item["kok_cart_id"],
                    "cart_type": "kok",
                    "quantity": cart_item.get("kok_quantity", 1)
                })
        
        # 홈쇼핑 장바구니 처리
        for cart_item in hs_cart_items:
            if hasattr(cart_item, 'product_name') and cart_item.product_name:
                cart_materials.append({
                    "material_name": cart_item.product_name,
                    "cart_id": cart_item.cart_id,
                    "cart_type": "homeshopping",
                    "quantity": getattr(cart_item, 'quantity', 1)
                })
                
    except Exception as e:
        logger.warning(f"장바구니 배치 조회 실패: {str(e)}")
    
    # 4. ingredient_matcher를 사용하여 매칭
    from services.recipe.utils.ingredient_matcher import IngredientStatusMatcher
    
    matcher = IngredientStatusMatcher()
    
    # 주문 내역과 매칭
    order_matches = matcher.match_orders_to_ingredients(
        [name for names in recipe_materials.values() for name in names],
        [
            {
                "order_id": m["order_id"],
                "order_time": m["order_date"],
                "kok_orders": [{"product_name": m["material_name"]}] if m["order_type"] == "kok" else [],
                "homeshopping_orders": [{"product_name": m["material_name"]}] if m["order_type"] == "homeshopping" else []
            }
            for m in owned_materials
        ]
    )
    
    # 장바구니와 매칭
    owned_material_names = set(order_matches.keys())
    cart_matches = matcher.match_cart_to_ingredients(
        [name for names in recipe_materials.values() for name in names],
        [(item, item["material_name"]) for item in cart_materials if item["cart_type"] == "kok"],
        [(item, item["material_name"]) for item in cart_materials if item["cart_type"] == "homeshopping"],
        exclude_owned=list(owned_material_names)
    )
    
    # 5. 각 레시피별로 재료 상태 결정
    result = {}
    for recipe_id, material_names in recipe_materials.items():
        ingredients_status, summary = matcher.determine_ingredient_status(
            material_names, order_matches, cart_matches
        )
        
        result[recipe_id] = {
            "ingredients_status": ingredients_status,
            "summary": summary
        }
    
    return result


async def _batch_fetch_kok_images(db: AsyncSession, product_ids: List[int]) -> Dict[int, str]:
    """
    콕 상품 이미지를 배치로 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        product_ids: 조회할 상품 ID 목록
    
    Returns:
        Dict[int, str]: product_id를 키로 하는 이미지 URL
    """
    if not product_ids:
        return {}
    
    # 각 상품의 첫 번째 이미지를 한 번에 조회
    stmt = (
        select(KokImageInfo.kok_product_id, KokImageInfo.kok_img_url)
        .where(KokImageInfo.kok_product_id.in_(product_ids))
        .distinct(KokImageInfo.kok_product_id)
        .order_by(KokImageInfo.kok_product_id, KokImageInfo.sort_order)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # product_id를 키로 하는 딕셔너리로 변환
    return {row.kok_product_id: row.kok_img_url for row in rows}


async def _batch_fetch_hs_images(db: AsyncSession, product_ids: List[int]) -> Dict[int, str]:
    """
    홈쇼핑 상품 이미지를 배치로 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        product_ids: 조회할 상품 ID 목록
    
    Returns:
        Dict[int, str]: product_id를 키로 하는 이미지 URL
    """
    if not product_ids:
        return {}
    
    # 각 상품의 첫 번째 이미지를 한 번에 조회
    stmt = (
        select(HomeshoppingImgUrl.product_id, HomeshoppingImgUrl.img_url)
        .where(HomeshoppingImgUrl.product_id.in_(product_ids))
        .distinct(HomeshoppingImgUrl.product_id)
        .order_by(HomeshoppingImgUrl.product_id, HomeshoppingImgUrl.sort_order)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # product_id를 키로 하는 딕셔너리로 변환
    return {row.product_id: row.img_url for row in rows}


async def get_user_order_counts(db: AsyncSession, user_id: int) -> int:
    """
    사용자별 주문 개수만 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        user_id: 조회할 사용자 ID
    
    Returns:
        int: 사용자의 주문 개수
        
    Note:
        - CRUD 계층: DB COUNT 쿼리만 실행하여 성능 최적화
        - 전체 주문 데이터를 가져오지 않고 개수만 계산
    """
    from sqlalchemy import func
    
    result = await db.execute(
        select(func.count(Order.order_id))
        .where(Order.user_id == user_id)
    )
    return result.scalar()


async def calculate_order_total_price(db: AsyncSession, order_id: int) -> int:
    """
    주문 ID로 총 주문 금액 계산 (콕 주문 + 홈쇼핑 주문)
    
    Args:
        db: 데이터베이스 세션
        order_id: 계산할 주문 ID
    
    Returns:
        int: 총 주문 금액
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 각 주문 타입별로 이미 계산된 order_price 사용
        - order_price가 없는 경우 계산 함수를 통해 재계산
        - 계산 실패 시 기본값(dc_price * quantity) 사용
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
                # 기본값 사용 (KokOrder는 dc_price가 없으므로 order_price가 없으면 0으로 처리)
                fallback_price = 0
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
    
    Args:
        url: 요청할 URL
        json: POST할 JSON 데이터
        timeout: 연결/읽기 통합 타임아웃(초, 기본값: 20.0)
    
    Returns:
        httpx.Response: HTTP 응답 객체
        
    Note:
        - httpx.AsyncClient를 context manager로 생성하여 커넥션 누수 방지
        - Content-Type: application/json 헤더 자동 설정
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=json, headers={"Content-Type": "application/json"})


async def _get_json(url: str, timeout: float = 15.0) -> httpx.Response:
    """
    비동기 HTTP GET 유틸
    
    Args:
        url: 요청할 URL
        timeout: 연결/읽기 통합 타임아웃(초, 기본값: 15.0)
    
    Returns:
        httpx.Response: HTTP 응답 객체
        
    Note:
        - httpx.AsyncClient 사용
        - 상세한 로깅을 통한 디버깅 지원
        - 예외 발생 시 에러 타입과 함께 로깅
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


async def _mark_all_children_payment_requested(
    db: AsyncSession,
    *,
    kok_orders: List[Any],
    hs_orders: List[Any],
    user_id: int,
) -> None:
    """
    하위 주문(콕/홈쇼핑)을 PAYMENT_REQUESTED로 일괄 갱신
    
    Args:
        db: 데이터베이스 세션
        kok_orders: 콕 주문 목록
        hs_orders: 홈쇼핑 주문 목록
        user_id: 상태 변경을 수행하는 사용자 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 기존 트랜잭션 사용 (새로운 트랜잭션 시작하지 않음)
        - 실패 시 상위에서 롤백 처리
        - 모든 하위 주문의 상태를 PAYMENT_REQUESTED로 변경
    """
    logger.info(f"하위 주문 상태를 PAYMENT_REQUESTED로 갱신 시작: kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 콕 주문 상태 갱신
    for k in kok_orders:
        try:
            await update_kok_order_status(
                db=db,
                kok_order_id=k.kok_order_id,
                new_status_code="PAYMENT_REQUESTED",
                changed_by=user_id,
            )
            logger.info(f"콕 주문 상태를 PAYMENT_REQUESTED로 갱신 완료: kok_order_id={k.kok_order_id}")
        except Exception as e:
            logger.error(f"콕 주문 상태 갱신 실패: kok_order_id={k.kok_order_id}, error={str(e)}")
            raise
    
    # 홈쇼핑 주문 상태 갱신
    for h in hs_orders:
        try:
            await update_hs_order_status(
                db=db,
                homeshopping_order_id=h.homeshopping_order_id,
                new_status_code="PAYMENT_REQUESTED",
                changed_by=user_id,
            )
            logger.info(f"홈쇼핑 주문 상태를 PAYMENT_REQUESTED로 갱신 완료: hs_order_id={h.homeshopping_order_id}")
        except Exception as e:
            logger.error(f"홈쇼핑 주문 상태 갱신 실패: homeshopping_order_id={h.homeshopping_order_id}, error={str(e)}")
            raise
    
    logger.info(f"모든 하위 주문 상태를 PAYMENT_REQUESTED로 갱신 완료")


async def _mark_all_children_payment_completed(
    db: AsyncSession,
    *,
    kok_orders: List[Any],
    hs_orders: List[Any],
    user_id: int,
) -> None:
    """
    하위 주문(콕/홈쇼핑)을 PAYMENT_COMPLETED로 일괄 갱신
    
    Args:
        db: 데이터베이스 세션
        kok_orders: 콕 주문 목록
        hs_orders: 홈쇼핑 주문 목록
        user_id: 상태 변경을 수행하는 사용자 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 기존 트랜잭션 사용 (새로운 트랜잭션 시작하지 않음)
        - 실패 시 상위에서 롤백 처리
        - 모든 하위 주문의 상태를 PAYMENT_COMPLETED로 변경
    """
    logger.info(f"하위 주문 상태를 PAYMENT_COMPLETED로 갱신 시작: kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 콕 주문 상태 갱신
    for k in kok_orders:
        try:
            await update_kok_order_status(
                db=db,
                kok_order_id=k.kok_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
            logger.info(f"콕 주문 상태를 PAYMENT_COMPLETED로 갱신 완료: kok_order_id={k.kok_order_id}")
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
            logger.info(f"홈쇼핑 주문 상태를 PAYMENT_COMPLETED로 갱신 완료: hs_order_id={h.homeshopping_order_id}")
        except Exception as e:
            logger.error(f"홈쇼핑 주문 상태 갱신 실패: homeshopping_order_id={h.homeshopping_order_id}, error={str(e)}")
            raise
    
    logger.info(f"모든 하위 주문 상태를 PAYMENT_COMPLETED로 갱신 완료")


async def _ensure_order_access(db: AsyncSession, order_id: int, user_id: int) -> Dict[str, Any]:
    """
    주문 존재/권한 확인 유틸
    
    Args:
        db: 데이터베이스 세션
        order_id: 확인할 주문 ID
        user_id: 요청한 사용자 ID
    
    Returns:
        Dict[str, Any]: 주문 데이터 (권한이 있는 경우)
        
    Raises:
        HTTPException: 주문이 없거나 권한이 없는 경우 404
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 해당 order_id가 존재하고, 소유자가 user_id인지 확인
        - 권한이 없으면 404 에러 반환
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

async def cancel_order(db: AsyncSession, order_id: int, reason: str):
    """
    주문을 취소하는 함수
    
    Args:
        db: 데이터베이스 세션
        order_id: 취소할 주문 ID
        reason: 취소 사유 (기본값: "결제 시간 초과")
    
    Returns:
        dict: 취소 결과 정보 (order_id, cancel_time, reason, cancelled_kok_orders, cancelled_hs_orders)
        
    Note:
        - CRUD 계층: DB 상태 변경 담당
        - 주문의 cancel_time을 현재 시간으로 설정
        - 모든 하위 주문(콕/홈쇼핑)의 상태를 CANCELLED로 변경
        - 상태 변경 이력을 StatusHistory 테이블에 기록
    """
    try:
        # 주문 조회
        order_result = await db.execute(
            select(Order)
            .where(Order.order_id == order_id)
        )
        order = order_result.scalar_one_or_none()
        
        if not order:
            raise ValueError(f"주문을 찾을 수 없습니다: {order_id}")
        
        # 취소 시간 설정
        current_time = datetime.utcnow()
        
        # cancel_time 업데이트
        order.cancel_time = current_time
        
        # 하위 주문들 조회
        kok_orders_result = await db.execute(
            select(KokOrder)
            .where(KokOrder.order_id == order_id)
        )
        kok_orders = kok_orders_result.scalars().all()
        
        hs_orders_result = await db.execute(
            select(HomeShoppingOrder)
            .where(HomeShoppingOrder.order_id == order_id)
        )
        hs_orders = hs_orders_result.scalars().all()
        
        # 콕 주문 상태를 CANCELLED로 업데이트
        for kok_order in kok_orders:
            # 상태 히스토리에 CANCELLED 기록 추가
            new_status_history = KokOrderStatusHistory(
                kok_order_id=kok_order.kok_order_id,
                status_id=await _get_status_id_by_code(db, "CANCELLED"),
                changed_at=current_time,
                changed_by=1  # 시스템 자동 취소
            )
            db.add(new_status_history)
        
        # 홈쇼핑 주문 상태를 CANCELLED로 업데이트
        for hs_order in hs_orders:
            # 상태 히스토리에 CANCELLED 기록 추가
            new_status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=hs_order.homeshopping_order_id,
                status_id=await _get_status_id_by_code(db, "CANCELLED"),
                changed_at=current_time,
                changed_by=1  # 시스템 자동 취소
            )
            db.add(new_status_history)
        
        await db.commit()
        
        logger.info(f"주문 취소 완료: order_id={order_id}, cancel_time={current_time}, reason={reason}")
        
        return {
            "order_id": order_id,
            "cancel_time": current_time,
            "reason": reason,
            "cancelled_kok_orders": len(kok_orders),
            "cancelled_hs_orders": len(hs_orders)
        }
        
    except Exception as e:
        logger.error(f"주문 취소 실패: order_id={order_id}, error={str(e)}")
        raise

async def _get_status_id_by_code(db: AsyncSession, status_code: str) -> int:
    """
    상태 코드로 status_id를 조회하는 헬퍼 함수
    
    Args:
        db: 데이터베이스 세션
        status_code: 조회할 상태 코드 (예: "CANCELLED", "PAYMENT_COMPLETED")
    
    Returns:
        int: 해당 상태 코드의 status_id
        
    Raises:
        ValueError: 상태 코드를 찾을 수 없는 경우
        
    Note:
        - StatusMaster 테이블에서 status_code로 status_id 조회
        - 주문 취소 시 CANCELLED 상태 ID 조회에 사용
    """
    status_result = await db.execute(
        select(StatusMaster.status_id)
        .where(StatusMaster.status_code == status_code)
    )
    status_id = status_result.scalar_one_or_none()
    if not status_id:
        raise ValueError(f"상태 코드를 찾을 수 없습니다: {status_code}")
    return status_id

async def get_recent_orders_with_ingredients(
    db: AsyncSession, 
    user_id: int, 
    days: int = 7
) -> dict:
    """
    7일 내 주문 내역에서 모든 상품의 product_name을 가져와서 키워드를 추출
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        days: 조회 기간 (일), 기본값 7일
        
    Returns:
        키워드 추출 결과 딕셔너리
    """
    logger.info(f"최근 {days}일 주문 내역 키워드 추출 시작: user_id={user_id}")
    
    # 7일 전 날짜 계산
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 주문 기본 정보 조회 (7일 내)
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .where(Order.order_time >= cutoff_date)
        .where(Order.cancel_time.is_(None))  # 취소되지 않은 주문만
        .order_by(Order.order_time.desc())
    )
    orders = result.scalars().all()
    
    # ingredient_matcher 초기화
    from services.recipe.utils.ingredient_matcher import IngredientKeywordExtractor
    ingredient_extractor = IngredientKeywordExtractor()
    
    all_products = []
    all_keywords = set()
    keyword_products = {}  # 키워드별로 어떤 상품에서 추출되었는지 추적
    
    for order in orders:
        # 콕 주문 처리
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_orders = kok_result.scalars().all()
        
        for kok_order in kok_orders:
            try:
                # 상품 기본 정보 조회
                product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == kok_order.kok_product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product and product.kok_product_name:
                    product_name = product.kok_product_name
                    
                    # 키워드 추출
                    extracted_keywords = ingredient_extractor.extract_keywords(product_name)
                    
                    # 결과 저장
                    product_info = {
                        "order_id": order.order_id,
                        "order_time": order.order_time,
                        "product_id": kok_order.kok_product_id,
                        "product_name": product_name,
                        "product_type": "kok",
                        "quantity": kok_order.quantity,
                        "price": kok_order.order_price,
                        "extracted_keywords": extracted_keywords,
                        "keyword_count": len(extracted_keywords)
                    }
                    
                    all_products.append(product_info)
                    
                    # 키워드별 상품 추적
                    for keyword in extracted_keywords:
                        all_keywords.add(keyword)
                        if keyword not in keyword_products:
                            keyword_products[keyword] = []
                        keyword_products[keyword].append({
                            "product_name": product_name,
                            "product_type": "kok",
                            "order_time": order.order_time
                        })
                        
            except Exception as e:
                logger.warning(f"콕 주문 처리 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
        
        # 홈쇼핑 주문 처리
        homeshopping_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
        )
        homeshopping_orders = homeshopping_result.scalars().all()
        
        for hs_order in homeshopping_orders:
            try:
                # 상품 기본 정보 조회
                product_stmt = select(HomeshoppingList).where(HomeshoppingList.product_id == hs_order.product_id)
                product_result = await db.execute(product_stmt)
                product = product_result.scalar_one_or_none()
                
                if product and product.product_name:
                    product_name = product.product_name
                    
                    # 키워드 추출
                    extracted_keywords = ingredient_extractor.extract_keywords(product_name)
                    
                    # 결과 저장
                    product_info = {
                        "order_id": order.order_id,
                        "order_time": order.order_time,
                        "product_id": hs_order.product_id,
                        "product_name": product_name,
                        "product_type": "homeshopping",
                        "quantity": hs_order.quantity,
                        "price": hs_order.order_price,
                        "extracted_keywords": extracted_keywords,
                        "keyword_count": len(extracted_keywords)
                    }
                    
                    all_products.append(product_info)
                    
                    # 키워드별 상품 추적
                    for keyword in extracted_keywords:
                        all_keywords.add(keyword)
                        if keyword not in keyword_products:
                            keyword_products[keyword] = []
                        keyword_products[keyword].append({
                            "product_name": product_name,
                            "product_type": "homeshopping",
                            "order_time": order.order_time
                        })
                        
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 처리 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
    
    # 키워드 통계 계산
    keyword_stats = {}
    for keyword in all_keywords:
        products = keyword_products[keyword]
        kok_count = len([p for p in products if p["product_type"] == "kok"])
        homeshopping_count = len([p for p in products if p["product_type"] == "homeshopping"])
        
        keyword_stats[keyword] = {
            "total_products": len(products),
            "kok_products": kok_count,
            "homeshopping_products": homeshopping_count,
            "products": products
        }
    
    # 결과 구성
    result = {
        "user_id": user_id,
        "days": days,
        "total_orders": len(orders),
        "total_products": len(all_products),
        "total_keywords": len(all_keywords),
        "products": all_products,
        "keywords": list(all_keywords),
        "keyword_stats": keyword_stats,
        "summary": {
            "kok_products": len([p for p in all_products if p["product_type"] == "kok"]),
            "homeshopping_products": len([p for p in all_products if p["product_type"] == "homeshopping"]),
            "products_with_keywords": len([p for p in all_products if p["keyword_count"] > 0]),
            "products_without_keywords": len([p for p in all_products if p["keyword_count"] == 0])
        }
    }
    
    logger.info(f"최근 {days}일 주문 내역 키워드 추출 완료: 총 {len(all_products)}개 상품, {len(all_keywords)}개 키워드")
    return result
