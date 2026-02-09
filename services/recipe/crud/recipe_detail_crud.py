"""Recipe detail CRUD functions."""

from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.recipe.utils.inventory_recipe import get_recipe_url

logger = get_logger("recipe_crud")

async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> Optional[Dict]:
    """
    레시피 상세정보(+재료 리스트, recipe_url 포함) 반환 (최적화: Raw SQL 사용)
    """    
    # logger.info(f"레시피 상세정보 조회 시작: recipe_id={recipe_id}")
    
    # 최적화된 쿼리: 레시피와 재료 정보를 한 번에 조회
    sql_query = """
    SELECT 
        r.recipe_id,
        r.recipe_title,
        r.cooking_name,
        r.cooking_introduction,
        r.scrap_count,
        r.thumbnail_url,
        r.cooking_case_name,
        r.cooking_category_name,
        r.number_of_serving,
        m.material_id,
        m.material_name,
        m.measure_amount,
        m.measure_unit
    FROM FCT_RECIPE r
    LEFT JOIN FCT_MTRL m ON r.recipe_id = m.recipe_id
    WHERE r.recipe_id = :recipe_id
    ORDER BY m.material_name
    """
    
    try:
        result = await db.execute(text(sql_query), {"recipe_id": recipe_id})
        rows = result.fetchall()
    except Exception as e:
        logger.error(f"레시피 상세정보 조회 SQL 실행 실패: recipe_id={recipe_id}, error={str(e)}")
        return None
    
    if not rows:
        logger.warning(f"레시피를 찾을 수 없음: recipe_id={recipe_id}")
        return None

    # 첫 번째 행에서 레시피 기본 정보 추출
    first_row = rows[0]
    recipe_dict = {
        "recipe_id": first_row.recipe_id,
        "recipe_title": first_row.recipe_title,
        "cooking_name": first_row.cooking_name,
        "cooking_introduction": first_row.cooking_introduction,
        "scrap_count": first_row.scrap_count,
        "thumbnail_url": first_row.thumbnail_url,
        "cooking_case_name": first_row.cooking_case_name,
        "cooking_category_name": first_row.cooking_category_name,
        "number_of_serving": first_row.number_of_serving,
        "recipe_url": get_recipe_url(recipe_id)
    }
    
    # 재료 정보 구성
    materials = []
    for row in rows:
        if row.material_name:  # 재료가 있는 경우만 추가
            materials.append({
                "material_id": row.material_id,
                "material_name": row.material_name,
                "measure_amount": row.measure_amount,
                "measure_unit": row.measure_unit
            })
    
    recipe_dict["materials"] = materials
    
    # logger.info(f"레시피 상세정보 조회 완료: recipe_id={recipe_id}, 재료 개수={len(materials)}")
    return recipe_dict

