from datetime import time, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .shared import logger

async def get_kok_product_name_by_id(db: AsyncSession, product_id: int) -> Optional[str]:
    """KOK 상품 ID로 상품명 조회"""
    try:
        query = text("""
            SELECT KOK_PRODUCT_NAME
            FROM FCT_KOK_PRODUCT_INFO
            WHERE KOK_PRODUCT_ID = :product_id
        """)
        
        result = await db.execute(query, {"product_id": product_id})
        row = result.fetchone()
        
        return row[0] if row else None
        
    except Exception as e:
        logger.error(f"KOK 상품명 조회 실패: product_id={product_id}, error={str(e)}")
        return None

async def get_homeshopping_recommendations_by_kok(
    db: AsyncSession, 
    kok_product_name: str, 
    search_terms: List[str], 
    k: int = 5
) -> List[Dict]:
    """KOK 상품명 기반으로 홈쇼핑 상품 추천"""
    try:
        if not search_terms:
            return []
        
        # 여러 검색어를 OR 조건으로 결합
        search_conditions = []
        params = {}
        
        for i, term in enumerate(search_terms):
            param_name = f"term_{i}"
            search_conditions.append(f"PRODUCT_NAME LIKE :{param_name}")
            params[param_name] = term
        
        # SQL 쿼리 구성 - FCT_HOMESHOPPING_PRODUCT_INFO와 FCT_HOMESHOPPING_LIST 테이블 조인
        query = text(f"""
            SELECT 
                p.PRODUCT_ID,
                c.PRODUCT_NAME,
                p.STORE_NAME,
                p.SALE_PRICE,
                p.DC_PRICE,
                p.DC_RATE,
                l.THUMB_IMG_URL,
                l.LIVE_DATE,
                l.LIVE_START_TIME,
                l.LIVE_END_TIME
            FROM FCT_HOMESHOPPING_PRODUCT_INFO p
            INNER JOIN HOMESHOPPING_CLASSIFY c ON p.PRODUCT_ID = c.PRODUCT_ID
            LEFT JOIN FCT_HOMESHOPPING_LIST l ON p.PRODUCT_ID = l.PRODUCT_ID
            WHERE c.CLS_FOOD = 1
              AND ({' OR '.join(search_conditions)})
            ORDER BY 
                CASE 
                    WHEN c.PRODUCT_NAME LIKE :exact_match THEN 1
                    WHEN c.PRODUCT_NAME LIKE :partial_match THEN 2
                    ELSE 3
                END,
                p.SALE_PRICE ASC
            LIMIT :limit
        """)
        
        # 파라미터 설정
        params = {}
        for i, condition in enumerate(search_conditions):
            # LIKE 조건에서 실제 검색어 추출
            if "LIKE '%" in condition and "%'" in condition:
                search_term = condition.split("LIKE '%")[1].split("%'")[0]
                params[f"term{i}"] = f"%{search_term}%"
        
        params.update({
            "exact_match": kok_product_name,
            "partial_match": f"{kok_product_name}%",
            "limit": k
        })
        
        result = await db.execute(query, params)
        rows = result.fetchall()
        
        # 결과를 딕셔너리 리스트로 변환
        recommendations = []
        for row in rows:
            # timedelta를 time으로 변환
            live_start_time = None
            live_end_time = None
            
            if row[8] is not None:  # LIVE_START_TIME
                if isinstance(row[8], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[8].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_start_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_start_time = row[8]
            
            if row[9] is not None:  # LIVE_END_TIME
                if isinstance(row[9], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[9].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_end_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_end_time = row[9]
            
            recommendations.append({
                "product_id": row[0],
                "product_name": row[1],
                "store_name": row[2],
                "sale_price": row[3],
                "dc_price": row[4],
                "dc_rate": row[5],
                "thumb_img_url": row[6],
                "live_date": row[7],
                "live_start_time": live_start_time,
                "live_end_time": live_end_time
            })
        
        return recommendations
        
    except Exception as e:
        logger.error(f"홈쇼핑 추천 조회 실패: kok_product_name='{kok_product_name}', error={str(e)}")
        return []

async def get_homeshopping_recommendations_fallback(
    db: AsyncSession, 
    kok_product_name: str, 
    k: int = 5
) -> List[Dict]:
    """폴백 추천: 상품명의 일부로 검색"""
    try:
        # 상품명에서 의미있는 부분 추출 (숫자, 특수문자 제거)
        import re
        clean_name = re.sub(r'[^\w가-힣]', ' ', kok_product_name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        if len(clean_name) < 2:
            return []
        
        # 2글자 이상의 연속된 문자열로 검색
        search_term = f"%{clean_name[:min(4, len(clean_name))]}%"
        
        query = text("""
            SELECT 
                p.PRODUCT_ID,
                c.PRODUCT_NAME,
                p.STORE_NAME,
                p.SALE_PRICE,
                p.DC_PRICE,
                p.DC_RATE,
                l.THUMB_IMG_URL,
                l.LIVE_DATE,
                l.LIVE_START_TIME,
                l.LIVE_END_TIME
            FROM FCT_HOMESHOPPING_PRODUCT_INFO p
            INNER JOIN HOMESHOPPING_CLASSIFY c ON p.PRODUCT_ID = c.PRODUCT_ID
            LEFT JOIN FCT_HOMESHOPPING_LIST l ON p.PRODUCT_ID = l.PRODUCT_ID
            WHERE c.CLS_FOOD = 1
              AND c.PRODUCT_NAME LIKE :search_term
            ORDER BY p.SALE_PRICE ASC
            LIMIT :limit
        """)
        
        result = await db.execute(query, {
            "search_term": search_term,
            "limit": k
        })
        rows = result.fetchall()
        
        # 결과를 딕셔너리 리스트로 변환
        recommendations = []
        for row in rows:
            # timedelta를 time으로 변환
            live_start_time = None
            live_end_time = None
            
            if row[8] is not None:  # LIVE_START_TIME
                if isinstance(row[8], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[8].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_start_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_start_time = row[8]
            
            if row[9] is not None:  # LIVE_END_TIME
                if isinstance(row[9], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[9].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_end_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_end_time = row[9]
            
            recommendations.append({
                "product_id": row[0],
                "product_name": row[1],
                "store_name": row[2],
                "sale_price": row[3],
                "dc_price": row[4],
                "dc_rate": row[5],
                "thumb_img_url": row[6],
                "live_date": row[7],
                "live_start_time": live_start_time,
                "live_end_time": live_end_time
            })
        
        return recommendations
        
    except Exception as e:
        logger.error(f"홈쇼핑 폴백 추천 조회 실패: kok_product_name='{kok_product_name}', error={str(e)}")
        return []
