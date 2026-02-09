"""Order listing read CRUD functions."""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.kok.kok_order_model import KokOrder
from services.order.models.homeshopping.hs_order_model import HomeShoppingOrder
from services.order.crud.common.order_image_support_crud import (
    _batch_fetch_kok_images,
    _batch_fetch_hs_images,
)
from services.order.crud.common.order_ingredient_support_crud import _batch_fetch_recipe_ingredients_status
from services.order.crud.common.order_recent_keyword_support_crud import get_recent_orders_with_ingredients

logger = get_logger("order_crud")

async def get_user_orders(db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0) -> list:
    """
    사용자별 주문 목록 조회 (최적화: 윈도우 함수 + Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        user_id: 조회할 사용자 ID
        limit: 조회할 주문 개수 (기본값: 20)
        offset: 건너뛸 주문 개수 (기본값: 0)
    
    Returns:
        list: 사용자의 주문 목록 (각 주문에 상품 이미지, 레시피 정보 포함)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 윈도우 함수와 Raw SQL을 사용하여 성능 최적화
        - 콕 주문: 상품 이미지, 레시피 정보, 재료 보유 현황 포함
        - 홈쇼핑 주문: 상품 이미지 포함
        - 최신 주문순으로 정렬
    """
    from sqlalchemy import text
    
    # 1. 먼저 order_id 목록을 limit/offset으로 조회
    order_ids_sql = """
    SELECT DISTINCT o.order_id, o.user_id, o.order_time, o.cancel_time
    FROM ORDERS o
    WHERE o.user_id = :user_id
    ORDER BY o.order_time DESC
    LIMIT :limit OFFSET :offset
    """
    
    # 2. 해당 order_id들에 대한 콕 주문 조회 (GROUP BY로 중복 제거)
    kok_orders_sql = """
    SELECT 
        o.order_id,
        o.user_id,
        o.order_time,
        o.cancel_time,
        ko.kok_order_id,
        ko.kok_product_id,
        ko.quantity,
        ko.order_price,
        ko.recipe_id,
        ko.kok_price_id,
        MAX(kpi.kok_product_name) as kok_product_name,
        MAX(kpi.kok_thumbnail) as kok_thumbnail,
        MAX(r.recipe_title) as recipe_title,
        MAX(r.cooking_introduction) as cooking_introduction,
        MAX(r.scrap_count) as scrap_count
    FROM ORDERS o
    INNER JOIN KOK_ORDERS ko ON o.order_id = ko.order_id
    LEFT JOIN FCT_KOK_PRODUCT_INFO kpi ON ko.kok_product_id = kpi.kok_product_id
    LEFT JOIN FCT_RECIPE r ON ko.recipe_id = r.recipe_id
    WHERE o.user_id = :user_id
    AND o.order_id IN :order_id_list
    GROUP BY o.order_id, o.user_id, o.order_time, o.cancel_time, ko.kok_order_id, ko.kok_product_id, ko.quantity, ko.order_price, ko.recipe_id, ko.kok_price_id
    ORDER BY o.order_time DESC, ko.kok_order_id
    """
    
    # 3. 해당 order_id들에 대한 홈쇼핑 주문 조회 (GROUP BY로 중복 제거)
    hs_orders_sql = """
    SELECT 
        o.order_id,
        o.user_id,
        o.order_time,
        o.cancel_time,
        ho.homeshopping_order_id,
        ho.product_id,
        ho.quantity,
        ho.order_price,
        ho.dc_price,
        MAX(hl.product_name) as product_name,
        MAX(hl.thumb_img_url) as thumb_img_url
    FROM ORDERS o
    INNER JOIN HOMESHOPPING_ORDERS ho ON o.order_id = ho.order_id
    LEFT JOIN FCT_HOMESHOPPING_LIST hl ON ho.product_id = hl.product_id
    WHERE o.user_id = :user_id
    AND o.order_id IN :order_id_list
    GROUP BY o.order_id, o.user_id, o.order_time, o.cancel_time, ho.homeshopping_order_id, ho.product_id, ho.quantity, ho.order_price, ho.dc_price
    ORDER BY o.order_time DESC, ho.homeshopping_order_id
    """
    
    # 1. 먼저 order_id 목록을 조회
    try:
        order_ids_result = await db.execute(text(order_ids_sql), {
            "user_id": user_id,
            "limit": limit,
            "offset": offset
        })
        order_ids_data = order_ids_result.fetchall()
    except Exception as e:
        logger.error(f"주문 ID 목록 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        return []
    
    if not order_ids_data:
        return []
    
    # order_id 목록 추출
    order_id_list = [row.order_id for row in order_ids_data]
    
    # 2. 해당 order_id들에 대한 콕 주문 조회
    try:
        kok_result = await db.execute(text(kok_orders_sql), {
            "user_id": user_id,
            "order_id_list": tuple(order_id_list)
        })
        kok_orders_data = kok_result.fetchall()
    except Exception as e:
        logger.error(f"콕 주문 목록 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        kok_orders_data = []
    
    # 3. 해당 order_id들에 대한 홈쇼핑 주문 조회
    try:
        hs_result = await db.execute(text(hs_orders_sql), {
            "user_id": user_id,
            "order_id_list": tuple(order_id_list)
        })
        hs_orders_data = hs_result.fetchall()
    except Exception as e:
        logger.error(f"홈쇼핑 주문 목록 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        hs_orders_data = []
    
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
    logger.debug(f"콕 주문 데이터 처리 시작: {len(kok_orders_data)}개 레코드")
    
    for row in kok_orders_data:
        logger.debug(f"콕 주문 레코드: order_id={row.order_id}, kok_order_id={row.kok_order_id}, kok_product_id={row.kok_product_id}")
        
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
            logger.debug(f"콕 주문 추가: order_id={row.order_id}, kok_order_id={row.kok_order_id}, 현재 개수={len(order_dict[row.order_id]['kok_orders'])}")
    
    # 홈쇼핑 주문 데이터 처리
    logger.debug(f"홈쇼핑 주문 데이터 처리 시작: {len(hs_orders_data)}개 레코드")
    
    for row in hs_orders_data:
        logger.debug(f"홈쇼핑 주문 레코드: order_id={row.order_id}, homeshopping_order_id={row.homeshopping_order_id}, product_id={row.product_id}")
        
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
            logger.debug(f"홈쇼핑 주문 추가: order_id={row.order_id}, homeshopping_order_id={row.homeshopping_order_id}, 현재 개수={len(order_dict[row.order_id]['homeshopping_orders'])}")
    
    # 9. 최신 주문순으로 정렬하여 반환
    order_list = list(order_dict.values())
    order_list.sort(key=lambda x: x["order_time"], reverse=True)
    
    return order_list


