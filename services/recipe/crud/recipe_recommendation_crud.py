"""Recipe recommendation CRUD functions based on inventory."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.recipe.models.core_model import Material, Recipe
from services.recipe.utils.inventory_recipe import (
    get_recipe_url,
    recommend_sequentially_for_inventory,
)

logger = get_logger("recipe_crud")

async def recommend_recipes_by_ingredients(
    db: AsyncSession,
    ingredients: List[str],
    amounts: List[float],
    units: List[str],
    page: int = 1,
    size: int = 10
) -> Tuple[List[Dict], int]:
    """
    재료명, 분량, 단위 기반 레시피 추천 (matched_ingredient_count 포함)
    - amount와 unit은 필수 파라미터
    - 페이지네이션(page, size)과 전체 개수(total) 반환
    - 순차적 재고 소진 알고리즘 적용
    - 효율적인 DB 쿼리로 타임아웃 방지
    """
    # logger.info(f"재료 기반 레시피 추천 시작: 재료={ingredients}, 분량={amounts}, 단위={units}, 페이지={page}, 크기={size}")
    
    # 기본 쿼리 (인기순)
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id)  # type: ignore
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))
    )
    
    # 순차적 재고 소진 알고리즘 적용
    # logger.info("순차적 재고 소진 알고리즘 모드")
    
    return await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )

async def recommend_recipes_combination_1(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10,
    user_id: Optional[int] = None
) -> Tuple[List[Dict], int]:
    """
    1조합: 전체 레시피 풀에서 가장 많은 재료 사용하는 순으로 선택
    - 사용자별로 다른 시드를 사용하여 다양한 결과 제공
    - 캐싱 추가로 성능 향상 (로직 변경 없음)
    """
    # logger.info(f"1조합 레시피 추천 시작: 재료={ingredients}, 분량={amounts}, 단위={units}, user_id={user_id}")
    
    # 캐시 비활성화 - 항상 Streamlit 로직 사용
    # if user_id:
    #     cached_result = recipe_cache.get_cached_result(
    #         user_id, ingredients, amounts or [], units or [], 1
    #     )
    #     if cached_result:
    #         recipes, total = cached_result
    #         return recipes, total
    
    # 기존 로직 그대로 유지
    # 사용자별로 다른 시드를 사용하여 다양한 결과 제공
    if user_id:
        seed = user_id % 3  # 사용자 ID를 3으로 나눈 나머지를 시드로 사용
    else:
        import time
        seed = int(time.time() // 60) % 3  # 시간 기반 시드 (fallback)
    
    # 시드 기반으로 정렬 기준 변경
    if seed == 0:
        # 인기순 정렬
        base_stmt = (
            select(Recipe)
            .join(Material, Recipe.recipe_id == Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Recipe.recipe_id)
            .order_by(desc(Recipe.scrap_count))
        )
    # logger.info(f"1조합: 인기순 정렬 사용 (시드: {seed})")
    elif seed == 1:
        # 최신순 정렬 (recipe_id 기준)
        base_stmt = (
            select(Recipe)
            .join(Material, Recipe.recipe_id == Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Recipe.recipe_id)
            .order_by(desc(Recipe.recipe_id))
        )
    # logger.info(f"1조합: 최신순 정렬 사용 (시드: {seed})")
    else:
        # 조합별 정렬 (재료 개수 + 인기도)
        base_stmt = (
            select(Recipe, func.count(Material.material_name).label('material_count'))
            .join(Material, Recipe.recipe_id == Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Recipe.recipe_id)
            .order_by(desc(func.count(Material.material_name)), desc(Recipe.scrap_count))
        )
    # logger.info(f"1조합: 재료 개수 + 인기도 정렬 사용 (시드: {seed})")
    
    # 기존 알고리즘 그대로 실행
    recipes, total = await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )
    
    # 캐시 저장 비활성화 - 항상 Streamlit 로직 사용
    # if user_id and recipes:
    #     recipe_cache.set_cached_result(
    #         user_id, ingredients, amounts or [], units or [], 1, recipes, total
    #     )
    
    return recipes, total

async def recommend_recipes_combination_2(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10,
    exclude_recipe_ids: List[int] = None,
    user_id: Optional[int] = None
) -> Tuple[List[Dict], int]:
    """
    2조합: 1조합에서 사용된 레시피를 제외한 나머지 레시피 풀에서 선택
    - 캐싱 추가로 성능 향상 (로직 변경 없음)
    """
    # logger.info(f"2조합 레시피 추천 시작: 재료={ingredients}, 제외할 레시피={exclude_recipe_ids}")
    
    # 캐시 비활성화 - 항상 Streamlit 로직 사용
    # if user_id and not exclude_recipe_ids:
    #     cached_result = recipe_cache.get_cached_result(
    #         user_id, ingredients, amounts or [], units or [], 2
    #     )
    #     if cached_result:
    #         recipes, total = cached_result
    #         return recipes, total
    
    # 기존 로직 그대로 유지
    # 1조합에서 사용된 레시피를 제외한 레시피 풀
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id)
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))  # 인기순 정렬
    )
    
    # 제외할 레시피가 있으면 쿼리에 추가
    if exclude_recipe_ids:
        base_stmt = base_stmt.where(Recipe.recipe_id.notin_(exclude_recipe_ids))
    # logger.info(f"제외할 레시피 ID: {exclude_recipe_ids}")
    
    # 기존 알고리즘 그대로 실행
    recipes, total = await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )
    
    # 캐시 저장 비활성화 - 항상 Streamlit 로직 사용
    # if user_id and recipes and not exclude_recipe_ids:
    #     recipe_cache.set_cached_result(
    #         user_id, ingredients, amounts or [], units or [], 2, recipes, total
    #     )
    
    return recipes, total

async def recommend_recipes_combination_3(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10,
    exclude_recipe_ids: List[int] = None,
    user_id: Optional[int] = None
) -> Tuple[List[Dict], int]:
    """
    3조합: 1조합, 2조합에서 사용된 레시피를 제외한 나머지 레시피 풀에서 선택
    - 캐싱 추가로 성능 향상 (로직 변경 없음)
    """
    # logger.info(f"3조합 레시피 추천 시작: 재료={ingredients}, 제외할 레시피={exclude_recipe_ids}")
    
    # 캐시 비활성화 - 항상 Streamlit 로직 사용
    # if user_id and not exclude_recipe_ids:
    #     cached_result = recipe_cache.get_cached_result(
    #         user_id, ingredients, amounts or [], units or [], 3
    #     )
    #     if cached_result:
    #         recipes, total = cached_result
    #         return recipes, total
    
    # 기존 로직 그대로 유지
    # 1조합, 2조합에서 사용된 레시피를 제외한 레시피 풀
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id)
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))  # 인기순 정렬
    )
    
    # 제외할 레시피가 있으면 쿼리에 추가
    if exclude_recipe_ids:
        base_stmt = base_stmt.where(Recipe.recipe_id.notin_(exclude_recipe_ids))
    # logger.info(f"제외할 레시피 ID: {exclude_recipe_ids}")
    
    # 기존 알고리즘 그대로 실행
    recipes, total = await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )
    
    # 캐시 저장 비활성화 - 항상 Streamlit 로직 사용
    # if user_id and recipes and not exclude_recipe_ids:
    #     recipe_cache.set_cached_result(
    #         user_id, ingredients, amounts or [], units or [], 3, recipes, total
    #     )
    
    return recipes, total

async def execute_standard_inventory_algorithm(
    db: AsyncSession,
    base_stmt,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10
) -> Tuple[List[Dict], int]:
    """
    모든 조합에서 공통으로 사용하는 표준 재고 소진 알고리즘
    - 후보 레시피는 이미 정렬되어 있음 (인기순/난이도순/시간순)
    - 선택 로직은 "가장 많은 재료 사용하는 순"으로 동일
    """
    # logger.info(f"표준 재고 소진 알고리즘 실행: 페이지={page}, 크기={size}")
    
    # 2-1. 초기 재고 설정
    initial_ingredients = []
    for i in range(len(ingredients)):
        try:
            # amounts가 제공된 경우 사용, 아니면 기본값 1
            if amounts and i < len(amounts):
                amount = float(amounts[i])
            else:
                amount = 1.0
        except (ValueError, TypeError):
            amount = 1.0
        
        # units가 제공된 경우 사용, 아니면 빈 문자열
        unit = units[i] if units and i < len(units) else ""
        
        initial_ingredients.append({
            'name': ingredients[i],
            'amount': amount,
            'unit': unit
        })
    
    # 2-2. 전체 후보 레시피를 한 번에 조회 (페이지네이션을 위해)
    # logger.info("전체 후보 레시피 조회 시작")
    candidate_recipes = (await db.execute(base_stmt)).scalars().unique().all()
    # logger.info(f"전체 후보 레시피 개수: {len(candidate_recipes)}")
    
    # 2-3. 레시피별 재료 정보를 효율적으로 조회
    recipe_ids = [r.recipe_id for r in candidate_recipes]
    materials_stmt = (
        select(Material)
        .where(Material.recipe_id.in_(recipe_ids))
    )
    all_materials = (await db.execute(materials_stmt)).scalars().all()
    
    # 레시피별 재료 맵 구성
    recipe_material_map = {}
    for mat in all_materials:
        if mat.recipe_id not in recipe_material_map:
            recipe_material_map[mat.recipe_id] = []
        
        try:
            amt = float(mat.measure_amount) if mat.measure_amount is not None else 0
        except (ValueError, TypeError):
            amt = 0
        
        recipe_material_map[mat.recipe_id].append({
            'mat': mat.material_name,
            'amt': amt,
            'unit': mat.measure_unit if mat.measure_unit else ''
        })
    
    # 2-4. 레시피 정보를 DataFrame 형태로 변환
    recipe_df = []
    for recipe in candidate_recipes:
        recipe_dict = {
            'RECIPE_ID': recipe.recipe_id,
            'RECIPE_TITLE': recipe.recipe_title,
            'COOKING_NAME': recipe.cooking_name,
            'SCRAP_COUNT': recipe.scrap_count,
            'RECIPE_URL': get_recipe_url(recipe.recipe_id),
            'THUMBNAIL_URL': recipe.thumbnail_url,
            'COOKING_CASE_NAME': recipe.cooking_case_name,
            'COOKING_CATEGORY_NAME': recipe.cooking_category_name,
            'COOKING_INTRODUCTION': recipe.cooking_introduction,
            'NUMBER_OF_SERVING': recipe.number_of_serving
        }
        recipe_df.append(recipe_dict)
    
    # DataFrame으로 변환 (measure_amount가 None인 경우 처리)
    try:
        recipe_df = pd.DataFrame(recipe_df)
    # logger.info(f"DataFrame 생성 완료: {len(recipe_df)}행")
    except Exception as e:
        logger.error(f"DataFrame 생성 실패: {e}")
        return [], 0
    
    # 2-5. mat2recipes 역인덱스 생성 (Streamlit 코드와 동일)
    mat2recipes = {}
    for rid, materials in recipe_material_map.items():
        for mat_info in materials:
            mat_name = mat_info['mat']
            if mat_name not in mat2recipes:
                mat2recipes[mat_name] = set()
            mat2recipes[mat_name].add(rid)
    
    # 2-6. 순차적 재고 소진 알고리즘 실행 (요청 페이지의 끝까지 생성하면 조기 중단)
    max_results_needed = page * size
    # logger.info(f"알고리즘 실행: 최대 {max_results_needed}개까지 생성")
    
    recommended, remaining_stock, early_stopped = recommend_sequentially_for_inventory(
        initial_ingredients,
        recipe_material_map,
        recipe_df,
        mat2recipes,
        max_results=max_results_needed
    )
    
    # logger.info(f"알고리즘 완료: {len(recommended)}개 생성, 조기중단: {early_stopped}")
    
    # 2-6. 페이지네이션 적용
    start, end = (page-1)*size, (page-1)*size + size
    paginated_recommended = recommended[start:end]
    
    # 2-7. 전체 개수 계산
    if early_stopped:
        # 조기중단이면 정확한 total 계산이 어려우므로 근사값 반환
        approx_total = (page - 1) * size + len(paginated_recommended) + 1
    # logger.info(f"조기중단으로 인한 근사 total: {approx_total}")
        return paginated_recommended, approx_total
    else:
        total = len(recommended)
    # logger.info(f"정확한 total: {total}")
        return paginated_recommended, total

