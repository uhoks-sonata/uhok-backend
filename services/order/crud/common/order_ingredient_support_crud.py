"""Order ingredient support CRUD functions."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.order_base_model import Order
from services.order.models.kok.kok_order_model import KokOrder
from services.order.models.homeshopping.hs_order_model import HomeShoppingOrder
from services.kok.models.product_model import KokProductInfo
from services.homeshopping.models.core_model import HomeshoppingList
from services.recipe.models.core_model import Material

logger = get_logger("order_crud")

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
    try:
        materials_stmt = select(Material).where(Material.recipe_id.in_(recipe_ids))
        materials_result = await db.execute(materials_stmt)
        materials = materials_result.scalars().all()
    except Exception as e:
        logger.error(f"재료 정보 배치 조회 SQL 실행 실패: recipe_ids={recipe_ids}, error={str(e)}")
        return {}
    
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
    
    # 순차적으로 주문 정보 조회 (SQLAlchemy AsyncSession은 동시 실행 불가)
    try:
        kok_result = await db.execute(kok_orders_stmt)
        kok_orders = kok_result.all()
    except Exception as e:
        logger.warning(f"콕 주문 배치 조회 실패: user_id={user_id}, error={str(e)}")
        kok_orders = []
    
    try:
        hs_result = await db.execute(hs_orders_stmt)
        hs_orders = hs_result.all()
    except Exception as e:
        logger.warning(f"홈쇼핑 주문 배치 조회 실패: user_id={user_id}, error={str(e)}")
        hs_orders = []
    
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
        from services.kok.crud.cart_crud import get_kok_cart_items
        from services.homeshopping.crud.cart_crud import get_homeshopping_cart_items
        
        # 순차적으로 장바구니 정보 조회 (SQLAlchemy AsyncSession은 동시 실행 불가)
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
