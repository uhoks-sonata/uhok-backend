"""Recipe ingredient-status CRUD functions."""

from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import get_settings
from common.keyword_extraction import (
    extract_homeshopping_keywords,
    extract_kok_keywords,
    load_ing_vocab,
    parse_mariadb_url,
)
from common.logger import get_logger

logger = get_logger("recipe_crud")

async def fetch_recipe_ingredients_status(
    db: AsyncSession, 
    recipe_id: int, 
    user_id: int
) -> Dict:
    """
    레시피의 식재료 상태 조회 (최적화: Raw SQL 사용)
    - 보유: 최근 7일 내 주문한 상품 / 재고 소진에 입력한 식재료
    - 장바구니: 현재 장바구니에 담긴 상품
    - 미보유: 레시피 식재료 중 보유/장바구니 상태를 제외한 식재료
    """    
    # logger.info(f"레시피 식재료 상태 조회 시작: recipe_id={recipe_id}, user_id={user_id}")
    
    # 최적화된 쿼리: 레시피 재료와 주문/장바구니 정보를 한 번에 조회
    sql_query = """
    WITH recipe_materials AS (
        SELECT material_name
        FROM FCT_MTRL
        WHERE recipe_id = :recipe_id
    ),
    recent_orders AS (
        SELECT 
            o.order_id,
            o.order_time,
            ko.kok_product_id,
            kpi.kok_product_name,
            'kok' as order_type
        FROM ORDERS o
        INNER JOIN KOK_ORDERS ko ON o.order_id = ko.order_id
        INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON ko.kok_product_id = kpi.kok_product_id
        WHERE o.user_id = :user_id
        AND o.order_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND o.cancel_time IS NULL
        
        UNION ALL
        
        SELECT 
            o.order_id,
            o.order_time,
            ho.product_id as kok_product_id,
            hl.product_name as kok_product_name,
            'homeshopping' as order_type
        FROM ORDERS o
        INNER JOIN HOMESHOPPING_ORDERS ho ON o.order_id = ho.order_id
        INNER JOIN FCT_HOMESHOPPING_LIST hl ON ho.product_id = hl.product_id
        WHERE o.user_id = :user_id
        AND o.order_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND o.cancel_time IS NULL
    ),
    cart_items AS (
        SELECT 
            kc.kok_cart_id,
            kpi.kok_product_name,
            kc.kok_quantity,
            'kok' as cart_type
        FROM KOK_CART kc
        INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON kc.kok_product_id = kpi.kok_product_id
        WHERE kc.user_id = :user_id
        
        UNION ALL
        
        SELECT 
            hc.cart_id as kok_cart_id,
            hl.product_name as kok_product_name,
            hc.quantity as kok_quantity,
            'homeshopping' as cart_type
        FROM HOMESHOPPING_CART hc
        INNER JOIN FCT_HOMESHOPPING_LIST hl ON hc.product_id = hl.product_id
        WHERE hc.user_id = :user_id
    )
    SELECT 
        rm.material_name,
        ro.order_id,
        ro.order_time,
        ro.kok_product_name,
        ro.order_type,
        ci.kok_cart_id,
        ci.kok_quantity,
        ci.cart_type
    FROM recipe_materials rm
    LEFT JOIN recent_orders ro ON rm.material_name = ro.kok_product_name
    LEFT JOIN cart_items ci ON rm.material_name = ci.kok_product_name
    ORDER BY rm.material_name
    """
    
    try:
        result = await db.execute(text(sql_query), {
            "recipe_id": recipe_id,
            "user_id": user_id
        })
        rows = result.fetchall()
    except Exception as e:
        logger.error(f"레시피 식재료 상태 조회 SQL 실행 실패: recipe_id={recipe_id}, user_id={user_id}, error={str(e)}")
        return {
            "recipe_id": recipe_id,
            "user_id": user_id,
            "ingredients_status": {"owned": [], "cart": [], "not_owned": []},
            "summary": {"total_ingredients": 0, "owned_count": 0, "cart_count": 0, "not_owned_count": 0}
        }
    
    if not rows:
        logger.warning(f"레시피 {recipe_id}의 식재료를 찾을 수 없음")
        return {
            "recipe_id": recipe_id,
            "user_id": user_id,
            "ingredients_status": {"owned": [], "cart": [], "not_owned": []},
            "summary": {"total_ingredients": 0, "owned_count": 0, "cart_count": 0, "not_owned_count": 0}
        }
    
    # 재료별로 상태 분류
    material_status = {}
    for row in rows:
        material_name = row.material_name
        if material_name not in material_status:
            material_status[material_name] = {
                "owned": [],
                "cart": [],
                "not_owned": []
            }
        
        # 주문 정보가 있는 경우 (보유 상태)
        if row.order_id:
            material_status[material_name]["owned"].append({
                "order_id": row.order_id,
                "order_time": row.order_time,
                "product_name": row.kok_product_name,
                "order_type": row.order_type
            })
        
        # 장바구니 정보가 있는 경우 (장바구니 상태)
        if row.kok_cart_id:
            material_status[material_name]["cart"].append({
                "cart_id": row.kok_cart_id,
                "product_name": row.kok_product_name,
                "quantity": row.kok_quantity,
                "cart_type": row.cart_type
            })
    
    # 최종 상태 결정
    ingredients_status = {"owned": [], "cart": [], "not_owned": []}
    owned_count = 0
    cart_count = 0
    not_owned_count = 0
    
    for material_name, status in material_status.items():
        if status["owned"]:
            ingredients_status["owned"].append({
                "material_name": material_name,
                "status": "owned",
                "order_info": status["owned"][0]  # 첫 번째 주문 정보 사용
            })
            owned_count += 1
        elif status["cart"]:
            ingredients_status["cart"].append({
                "material_name": material_name,
                "status": "cart",
                "cart_info": status["cart"][0]  # 첫 번째 장바구니 정보 사용
            })
            cart_count += 1
        else:
            ingredients_status["not_owned"].append({
                "material_name": material_name,
                "status": "not_owned"
            })
            not_owned_count += 1
    
    summary = {
        "total_ingredients": len(material_status),
        "owned_count": owned_count,
        "cart_count": cart_count,
        "not_owned_count": not_owned_count
    }
    
    result = {
        "recipe_id": recipe_id,
        "user_id": user_id,
        "ingredients_status": ingredients_status,
        "summary": summary
    }
    
    # logger.info(f"레시피 식재료 상태 조회 완료: recipe_id={recipe_id}, 총 재료={summary['total_ingredients']}, 보유={summary['owned_count']}, 장바구니={summary['cart_count']}, 미보유={summary['not_owned_count']}")
    return result


async def get_recipe_ingredients_status(
    db: AsyncSession, 
    user_id: int, 
    recipe_id: int
) -> Optional[Dict]:
    """
    레시피의 식재료별 사용자 보유/장바구니/미보유 상태 조회 (키워드 추출 방식)
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        recipe_id: 레시피 ID
        
    Returns:
        식재료 상태 정보 딕셔너리
    """
   
    # logger.info(f"레시피 식재료 상태 조회 시작: user_id={user_id}, recipe_id={recipe_id}")
    
    try:
        # 1. 레시피 재료 조회
        recipe_sql = """
        SELECT material_name
        FROM FCT_MTRL
        WHERE recipe_id = :recipe_id
        """
        recipe_result = await db.execute(text(recipe_sql), {"recipe_id": recipe_id})
        recipe_rows = recipe_result.fetchall()
        
        if not recipe_rows:
            logger.warning(f"레시피를 찾을 수 없음: recipe_id={recipe_id}")
            return {
                "recipe_id": recipe_id,
                "user_id": user_id,
                "ingredients": [],
                "summary": {"total_ingredients": 0, "owned_count": 0, "cart_count": 0, "not_owned_count": 0}
            }
        
        # 2. 최근 7일 주문 내역 조회
        orders_sql = """
        SELECT 
            o.order_id,
            o.order_time,
            ko.kok_product_id,
            kpi.kok_product_name,
            ko.quantity,
            'kok' as order_type
        FROM ORDERS o
        INNER JOIN KOK_ORDERS ko ON o.order_id = ko.order_id
        INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON ko.kok_product_id = kpi.kok_product_id
        WHERE o.user_id = :user_id
        AND o.order_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND o.cancel_time IS NULL
        
        UNION ALL
        
        SELECT 
            o.order_id,
            o.order_time,
            ho.product_id as kok_product_id,
            hl.product_name as kok_product_name,
            ho.quantity,
            'homeshopping' as order_type
        FROM ORDERS o
        INNER JOIN HOMESHOPPING_ORDERS ho ON o.order_id = ho.order_id
        INNER JOIN FCT_HOMESHOPPING_LIST hl ON ho.product_id = hl.product_id
        WHERE o.user_id = :user_id
        AND o.order_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND o.cancel_time IS NULL
        """
        orders_result = await db.execute(text(orders_sql), {"user_id": user_id})
        orders_rows = orders_result.fetchall()
        
        # 3. 장바구니 조회
        cart_sql = """
        SELECT 
            kc.kok_cart_id,
            kpi.kok_product_name,
            kc.kok_quantity,
            'kok' as cart_type
        FROM KOK_CART kc
        INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON kc.kok_product_id = kpi.kok_product_id
        WHERE kc.user_id = :user_id
        """
        cart_result = await db.execute(text(cart_sql), {"user_id": user_id})
        cart_rows = cart_result.fetchall()
        
        # 4. 표준 재료 어휘 로드
        ing_vocab = load_ing_vocab(parse_mariadb_url(get_settings().mariadb_service_url))
        
        # 5. 재료별 상태 매칭
        material_status = {}
        
        for recipe_row in recipe_rows:
            material_name = recipe_row.material_name
            material_status[material_name] = {
                "owned": [],
                "cart": [],
                "status": "not_owned"
            }
            
            # 주문 내역에서 매칭
            for order_row in orders_rows:
                product_name = order_row.kok_product_name
                order_type = order_row.order_type
                
                # 키워드 추출
                if order_type == "kok":
                    keywords_result = extract_kok_keywords(product_name, ing_vocab)
                else:  # homeshopping
                    keywords_result = extract_homeshopping_keywords(product_name, ing_vocab)
                
                keywords = keywords_result.get("keywords", [])
                
                # 재료명과 매칭 확인
                if material_name in keywords:
                    material_status[material_name]["owned"].append({
                        "order_id": order_row.order_id,
                        "order_date": order_row.order_time,
                        "product_name": product_name,
                        "quantity": order_row.quantity,
                        "order_type": order_type
                    })
                    material_status[material_name]["status"] = "owned"
            
            # 장바구니에서 매칭 (보유가 아닌 경우에만)
            if material_status[material_name]["status"] != "owned":
                for cart_row in cart_rows:
                    product_name = cart_row.kok_product_name
                    
                    # 키워드 추출
                    keywords_result = extract_kok_keywords(product_name, ing_vocab)
                    keywords = keywords_result.get("keywords", [])
                    
                    # 재료명과 매칭 확인
                    if material_name in keywords:
                        material_status[material_name]["cart"].append({
                            "cart_id": cart_row.kok_cart_id,
                            "product_name": product_name,
                            "quantity": cart_row.kok_quantity,
                            "cart_type": cart_row.cart_type
                        })
                        material_status[material_name]["status"] = "cart"
        
        # 6. 최종 결과 생성
        ingredients_status = []
        owned_count = 0
        cart_count = 0
        not_owned_count = 0
        
        for material_name, status in material_status.items():
            order_info = None
            cart_info = None
            status_type = status["status"]
            
            if status_type == "owned":
                order_info = status["owned"][0] if status["owned"] else None
                owned_count += 1
            elif status_type == "cart":
                cart_info = status["cart"][0] if status["cart"] else None
                cart_count += 1
            else:
                not_owned_count += 1
            
            ingredients_status.append({
                "material_name": material_name,
                "status": status_type,
                "order_info": order_info,
                "cart_info": cart_info
            })
        
        # 요약 정보 생성
        summary = {
            "total_ingredients": len(material_status),
            "owned_count": owned_count,
            "cart_count": cart_count,
            "not_owned_count": not_owned_count
        }
        
        result = {
            "recipe_id": recipe_id,
            "user_id": user_id,
            "ingredients": ingredients_status,
            "summary": summary
        }
        
        # logger.info(f"레시피 식재료 상태 조회 완료: recipe_id={recipe_id}, 총 재료={len(material_status)}, 보유={owned_count}, 장바구니={cart_count}, 미보유={not_owned_count}")
        
        return result
        
    except Exception as e:
        logger.error(f"레시피 식재료 상태 조회 실패: user_id={user_id}, recipe_id={recipe_id}, error={str(e)}")
        return None

