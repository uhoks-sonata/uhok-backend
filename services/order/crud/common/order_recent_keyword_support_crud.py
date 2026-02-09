"""Order recent-keyword support CRUD functions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger

logger = get_logger("order_crud")

async def get_recent_orders_with_ingredients(
    db: AsyncSession, 
    user_id: int, 
    days: int = 7
) -> dict:
    """
    7일 내 주문 내역에서 모든 상품의 product_name을 가져와서 키워드를 추출 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        days: 조회 기간 (일), 기본값 7일
        
    Returns:
        키워드 추출 결과 딕셔너리
    """
    from sqlalchemy import text
    from datetime import datetime, timedelta
    
    # 7일 전 날짜 계산
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # 최적화된 쿼리: Raw SQL을 사용하여 모든 상품 정보를 한 번에 조회
    sql_query = """
    WITH recent_orders AS (
        SELECT DISTINCT o.order_id, o.order_time
        FROM ORDERS o
        WHERE o.user_id = :user_id
        AND o.order_time >= :cutoff_date
        AND o.cancel_time IS NULL
    ),
    kok_products AS (
        SELECT 
            ro.order_id,
            ro.order_time,
            ko.kok_order_id,
            ko.kok_product_id,
            ko.quantity,
            ko.order_price,
            kpi.kok_product_name,
            'kok' as product_type
        FROM recent_orders ro
        INNER JOIN KOK_ORDERS ko ON ro.order_id = ko.order_id
        INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON ko.kok_product_id = kpi.kok_product_id
        WHERE kpi.kok_product_name IS NOT NULL
    ),
    homeshopping_products AS (
        SELECT 
            ro.order_id,
            ro.order_time,
            ho.homeshopping_order_id,
            ho.product_id,
            ho.quantity,
            ho.order_price,
            hl.product_name,
            'homeshopping' as product_type
        FROM recent_orders ro
        INNER JOIN HOMESHOPPING_ORDERS ho ON ro.order_id = ho.order_id
        INNER JOIN FCT_HOMESHOPPING_LIST hl ON ho.product_id = hl.product_id
        WHERE hl.product_name IS NOT NULL
    )
    SELECT 
        order_id,
        order_time,
        kok_order_id,
        kok_product_id,
        homeshopping_order_id,
        product_id,
        quantity,
        order_price,
        COALESCE(kok_product_name, product_name) as product_name,
        COALESCE('kok', product_type) as product_type
    FROM kok_products
    UNION ALL
    SELECT 
        order_id,
        order_time,
        NULL as kok_order_id,
        NULL as kok_product_id,
        homeshopping_order_id,
        product_id,
        quantity,
        order_price,
        product_name,
        product_type
    FROM homeshopping_products
    ORDER BY order_time DESC
    """
    
    try:
        result = await db.execute(text(sql_query), {
            "user_id": user_id,
            "cutoff_date": cutoff_date
        })
        products_data = result.fetchall()
    except Exception as e:
        logger.error(f"최근 주문 조회 SQL 실행 실패: user_id={user_id}, days={days}, error={str(e)}")
        return {
            "user_id": user_id,
            "days": days,
            "total_orders": 0,
            "total_products": 0,
            "total_keywords": 0,
            "products": [],
            "keywords": [],
            "keyword_stats": {},
            "summary": {
                "kok_products": 0,
                "homeshopping_products": 0,
                "products_with_keywords": 0,
                "products_without_keywords": 0
            }
        }
    
    # ingredient_matcher 초기화
    from services.recipe.utils.ingredient_matcher import IngredientKeywordExtractor
    ingredient_extractor = IngredientKeywordExtractor()
    
    all_products = []
    all_keywords = set()
    keyword_products = {}  # 키워드별로 어떤 상품에서 추출되었는지 추적
    
    # 최적화된 처리: 이미 조회된 데이터를 직접 사용
    for row in products_data:
        try:
            product_name = row.product_name
            if not product_name:
                continue
            
            # 키워드 추출
            extracted_keywords = ingredient_extractor.extract_keywords(product_name)
            
            # 결과 저장
            product_info = {
                "order_id": row.order_id,
                "order_time": row.order_time,
                "product_id": row.kok_product_id or row.product_id,
                "product_name": product_name,
                "product_type": row.product_type,
                "quantity": row.quantity,
                "price": row.order_price,
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
                    "product_type": row.product_type,
                    "order_time": row.order_time
                })
                
        except Exception as e:
            logger.warning(f"상품 처리 실패: product_name={row.product_name}, error={str(e)}")
    
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
        "total_orders": len(set(row.order_id for row in products_data)),
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
    
    # logger.info(f"최근 {days}일 주문 내역 키워드 추출 완료: 총 {len(all_products)}개 상품, {len(all_keywords)}개 키워드")
    return result
