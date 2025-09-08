"""
레시피/재료/별점 DB 접근(CRUD) 함수
- 모든 recipe_url 생성은 get_recipe_url 함수로 일원화
- 중복 dict 변환 등 최소화
- 추천/유사도 계산은 recipe.utils의 포트(RecommenderPort)에 위임
- 데이터 액세스 계층: db.add(), db.delete() 등 DB 상태 변경 로직 수행
- 트랜잭션 관리(commit/rollback)는 상위 계층(router)에서 담당
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional, Dict, Tuple
import pandas as pd
from datetime import datetime, timedelta
import asyncio

from common.logger import get_logger
from services.recipe.utils.simple_cache import recipe_cache

from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder
from services.homeshopping.models.homeshopping_model import (
    HomeshoppingList, HomeshoppingProductInfo
)
from services.kok.models.kok_model import KokProductInfo
from services.recipe.models.recipe_model import (
    Recipe, Material, RecipeRating
)
# ⬇️ 추가: 추천 포트(로컬/원격 어댑터)는 라우터/서비스에서 DI로 주입하여 사용
from ..utils.ports import VectorSearcherPort

# ⬇️ 추가: 추천 관련 유틸리티 함수들
from ..utils.inventory_recipe import (
    get_recipe_url,
    recommend_sequentially_for_inventory
)

# 로거 초기화
logger = get_logger("recipe_crud")


async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> Optional[Dict]:
    """
    레시피 상세정보(+재료 리스트, recipe_url 포함) 반환 (최적화: Raw SQL 사용)
    """
    from sqlalchemy import text
    
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
        m.material_name,
        m.measure_amount,
        m.measure_unit
    FROM RECIPE r
    LEFT JOIN MATERIAL m ON r.recipe_id = m.recipe_id
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
                "material_name": row.material_name,
                "measure_amount": row.measure_amount,
                "measure_unit": row.measure_unit
            })
    
    recipe_dict["materials"] = materials
    
    # logger.info(f"레시피 상세정보 조회 완료: recipe_id={recipe_id}, 재료 개수={len(materials)}")
    return recipe_dict


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
    
    # 캐시에서 결과 조회 시도 (로직 변경 없음)
    if user_id:
        cached_result = recipe_cache.get_cached_result(
            user_id, ingredients, amounts or [], units or [], 1
        )
        if cached_result:
            recipes, total = cached_result
    # logger.info(f"1조합 캐시 히트: {len(recipes)}개 레시피")
            return recipes, total
    
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
    
    # 결과를 캐시에 저장 (로직 변경 없음)
    if user_id and recipes:
        recipe_cache.set_cached_result(
            user_id, ingredients, amounts or [], units or [], 1, recipes, total
        )
    
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
    
    # 캐시에서 결과 조회 시도 (제외할 레시피가 없는 경우만)
    if user_id and not exclude_recipe_ids:
        cached_result = recipe_cache.get_cached_result(
            user_id, ingredients, amounts or [], units or [], 2
        )
        if cached_result:
            recipes, total = cached_result
    # logger.info(f"2조합 캐시 히트: {len(recipes)}개 레시피")
            return recipes, total
    
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
    
    # 결과를 캐시에 저장 (제외할 레시피가 없는 경우만)
    if user_id and recipes and not exclude_recipe_ids:
        recipe_cache.set_cached_result(
            user_id, ingredients, amounts or [], units or [], 2, recipes, total
        )
    
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
    
    # 캐시에서 결과 조회 시도 (제외할 레시피가 없는 경우만)
    if user_id and not exclude_recipe_ids:
        cached_result = recipe_cache.get_cached_result(
            user_id, ingredients, amounts or [], units or [], 3
        )
        if cached_result:
            recipes, total = cached_result
    # logger.info(f"3조합 캐시 히트: {len(recipes)}개 레시피")
            return recipes, total
    
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
    
    # 결과를 캐시에 저장 (제외할 레시피가 없는 경우만)
    if user_id and recipes and not exclude_recipe_ids:
        recipe_cache.set_cached_result(
            user_id, ingredients, amounts or [], units or [], 3, recipes, total
        )
    
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


async def recommend_by_recipe_pgvector(
    *,
    mariadb: AsyncSession,
    postgres: AsyncSession,
    query: str,
    method: str = "recipe",
    top_k: int = 25,                      # (유지: 호환용, recipe 모드에선 page/size가 우선)
    vector_searcher: VectorSearcherPort,  # ⬅️ 포트 주입
    page: int = 1,                        # ⬅️ 추가: 1부터 시작
    size: int = 10,                       # ⬅️ 추가: 페이지당 개수(무한스크롤 단위)
    include_materials: bool = False,      # ⬅️ 추가: 재료를 한 컬럼에 리스트로 집계해서 붙일지
) -> pd.DataFrame:
    """
    pgvector 컬럼(Vector(384))을 사용하는 레시피/식재료 추천(비동기, 중복 제거, 페이지네이션).
    - method="recipe":
        1) MariaDB: 제목 부분/정확 일치 우선(RANK_TYPE=0, 인기순) — 현재 페이지까지 필요한 수량(page*size)만큼 수집
        2) PostgreSQL: pgvector <-> 연산으로 부족분 보완(RANK_TYPE=1, 거리 오름차순)
        3) MariaDB: 상세 정보 조인
        4) (옵션) 재료를 레시피당 리스트로 집계하여 한 컬럼으로 붙임(include_materials=True)
        5) 항상 "레시피당 1행", 페이지네이션(10개 기본)
    - method="ingredient":
        쉼표로 구분된 재료명을 모두 포함(AND)하는 레시피를 MariaDB에서 조회(유사도 없음).
        상세 조인 후 (옵션) 재료 집계.
    - 반환: 상세 정보가 포함된 DataFrame (No. 컬럼은 해당 페이지 내 1..N)
    """
    from sqlalchemy import select, desc  # 파일 상단에 있으면 제거 가능

    if method not in {"recipe", "ingredient"}:
        raise ValueError("method must be 'recipe' or 'ingredient'")

    page = max(1, int(page))
    size = max(1, int(size))
    fetch_upto = page * size  # 현재 페이지까지 필요한 총량

    # 캐시에서 검색 결과 조회 시도
    cached_result = recipe_cache.get_cached_search(query, method, page, size)
    if cached_result and 'recipes' in cached_result:
        logger.info(f"검색 결과 캐시 히트: {query[:20]}...")
        return pd.DataFrame(cached_result['recipes'])

    # ========================== method: ingredient ==========================
    if method == "ingredient":
        ingredients = [i.strip() for i in (query or "").split(",") if i.strip()]
        if not ingredients:
            return pd.DataFrame()

        # AND 포함(모든 재료 포함) — 최적화된 쿼리
        from sqlalchemy import func as sa_func
        ids_stmt = (
            select(Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Material.recipe_id)
            .having(sa_func.count(sa_func.distinct(Material.material_name)) == len(ingredients))
            .order_by(desc(sa_func.count(sa_func.distinct(Material.material_name))))  # 매칭된 재료 수로 정렬
        )
        
        # 페이지네이션을 위한 OFFSET/LIMIT 사용 (전체 데이터 조회 방지)
        start = (page - 1) * size
        ids_stmt = ids_stmt.offset(start).limit(size)
        
        ids_rows = await mariadb.execute(ids_stmt)
        page_ids = [int(rid) for (rid,) in ids_rows.all()]
        if not page_ids:
            return pd.DataFrame()

        detail_stmt = (
            select(
                Recipe.recipe_id.label("RECIPE_ID"),
                Recipe.recipe_title.label("RECIPE_TITLE"),
                Recipe.cooking_name.label("COOKING_NAME"),
                Recipe.scrap_count.label("SCRAP_COUNT"),
                Recipe.cooking_case_name.label("COOKING_CASE_NAME"),
                Recipe.cooking_category_name.label("COOKING_CATEGORY_NAME"),
                Recipe.cooking_introduction.label("COOKING_INTRODUCTION"),
                Recipe.number_of_serving.label("NUMBER_OF_SERVING"),
                Recipe.thumbnail_url.label("THUMBNAIL_URL"),
            )
            .where(Recipe.recipe_id.in_(page_ids))
        )
        detail_rows = (await mariadb.execute(detail_stmt)).all()
        final_df = pd.DataFrame(detail_rows, columns=[
            "RECIPE_ID","RECIPE_TITLE","COOKING_NAME","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
            "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
        ])

        # 페이지 순서 유지
        order_map = {rid: i for i, rid in enumerate(page_ids)}
        final_df["__order__"] = final_df["RECIPE_ID"].map(order_map).fillna(10**9)
        final_df = final_df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)

        # 번호 컬럼(페이지 기준)
        final_df.insert(0, "No.", range(1, len(final_df) + 1))

        # (옵션) 재료 집계 - N+1 문제 해결
        if include_materials and page_ids:
            # 배치로 재료 정보 조회 (N+1 문제 해결)
            m_stmt = select(
                Material.recipe_id, Material.material_name, Material.measure_amount, Material.measure_unit
            ).where(Material.recipe_id.in_(page_ids))
            m_rows = (await mariadb.execute(m_stmt)).all()
            if m_rows:
                m_df = pd.DataFrame(m_rows, columns=["RECIPE_ID","MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"])
                # 레시피별 재료 집계 최적화
                mats = (
                    m_df.groupby("RECIPE_ID")[["MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"]]
                    .apply(lambda g: g.to_dict("records"))
                    .rename("MATERIALS")
                    .reset_index()
                )
                final_df = final_df.merge(mats, on="RECIPE_ID", how="left")

        return final_df

    # ============================ method: recipe ============================
    # 1) 제목 검색과 벡터 검색을 병렬로 실행하여 성능 향상
    async def search_exact_matches():
        """정확한 제목 매치 검색"""
        name_col = getattr(Recipe, "cooking_name", None) or getattr(Recipe, "recipe_title")
        base_stmt = (
            select(Recipe.recipe_id, name_col.label("RECIPE_TITLE"), Recipe.scrap_count)
            .where(name_col.contains(query))
            .order_by(desc(Recipe.scrap_count))
            .limit(fetch_upto)
        )
        base_rows = (await mariadb.execute(base_stmt)).all()
        exact_df = pd.DataFrame(base_rows, columns=["RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT"]).drop_duplicates("RECIPE_ID")
        exact_df["RANK_TYPE"] = 0
        return exact_df

    async def search_vector_matches():
        """벡터 유사도 검색"""
        try:
            pairs = await vector_searcher.find_similar_ids(
                pg_db=postgres,
                query=query,
                top_k=fetch_upto + size * 2,  # 충분한 버퍼 제공
                exclude_ids=None,
            )
            return [rid for rid, _ in pairs]
        except Exception as e:
            logger.warning(f"벡터 검색 실패: {e}")
            return []

    # 병렬 실행으로 성능 향상
    exact_df, vec_ids = await asyncio.gather(
        search_exact_matches(),
        search_vector_matches()
    )

    exact_ids = [int(x) for x in exact_df["RECIPE_ID"].tolist()]
    need_after_exact = max(0, fetch_upto - len(exact_ids))

    # 3) ID 병합 → 중복 제거 → 페이지 슬라이스 (최적화)
    merged_ids: List[int] = []
    seen = set()
    
    # 정확한 매치를 우선으로 추가
    for rid in exact_ids:
        if rid not in seen:
            merged_ids.append(rid)
            seen.add(rid)
    
    # 벡터 검색 결과 추가 (필요한 만큼만)
    for rid in vec_ids:
        if rid not in seen and len(merged_ids) < fetch_upto:
            merged_ids.append(rid)
            seen.add(rid)

    start = (page - 1) * size
    page_ids = merged_ids[start : start + size]
    if not page_ids:
        return pd.DataFrame()

    # 4) 상세 정보 조회 최적화 (필요한 컬럼만 선택)
    detail_stmt = (
        select(
            Recipe.recipe_id.label("RECIPE_ID"),
            Recipe.recipe_title.label("RECIPE_TITLE"),
            Recipe.cooking_name.label("COOKING_NAME"),
            Recipe.scrap_count.label("SCRAP_COUNT"),
            Recipe.cooking_case_name.label("COOKING_CASE_NAME"),
            Recipe.cooking_category_name.label("COOKING_CATEGORY_NAME"),
            Recipe.cooking_introduction.label("COOKING_INTRODUCTION"),
            Recipe.number_of_serving.label("NUMBER_OF_SERVING"),
            Recipe.thumbnail_url.label("THUMBNAIL_URL"),
        )
        .where(Recipe.recipe_id.in_(page_ids))
    )
    detail_rows = (await mariadb.execute(detail_stmt)).all()
    detail_df = pd.DataFrame(detail_rows, columns=[
        "RECIPE_ID","RECIPE_TITLE","COOKING_NAME","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
        "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
    ])

    # 5) RANK_TYPE 부여(제목일치=0, 유사도=1) + 순서 유지 + 번호
    exact_set = set(exact_ids)
    detail_df["RANK_TYPE"] = detail_df["RECIPE_ID"].apply(lambda x: 0 if int(x) in exact_set else 1)

    order_map = {rid: i for i, rid in enumerate(page_ids)}
    detail_df["__order__"] = detail_df["RECIPE_ID"].map(order_map).fillna(10**9)
    final_df = detail_df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)
    final_df.insert(0, "No.", range(1, len(final_df) + 1))

    # 6) (옵션) 재료 집계 — 레시피당 1행 유지 (N+1 문제 해결)
    if include_materials and page_ids:
        # 배치로 재료 정보 조회 (N+1 문제 해결)
        m_stmt = select(
            Material.recipe_id, Material.material_name, Material.measure_amount, Material.measure_unit
        ).where(Material.recipe_id.in_(page_ids))
        m_rows = (await mariadb.execute(m_stmt)).all()
        if m_rows:
            m_df = pd.DataFrame(m_rows, columns=["RECIPE_ID","MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"])
            # 레시피별 재료 집계 최적화
            mats = (
                m_df.groupby("RECIPE_ID")[["MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"]]
                .apply(lambda g: g.to_dict("records"))
                .rename("MATERIALS")
                .reset_index()
            )
            detail_df = detail_df.merge(mats, on="RECIPE_ID", how="left")

    # 검색 결과를 캐시에 저장
    if not final_df.empty:
        cache_data = {
            'recipes': final_df.to_dict(orient="records"),
            'page': page,
            'size': size,
            'method': method
        }
        recipe_cache.set_cached_search(query, method, page, size, cache_data)

    return final_df


# async def recommend_by_recipe_pgvector(
#     *,
#     mariadb: AsyncSession,
#     postgres: AsyncSession,
#     query: str,
#     method: str = "recipe",
#     top_k: int = 25,
#     vector_searcher: VectorSearcherPort,   # ⬅️ 포트 주입
# ) -> pd.DataFrame:
#     """
#     pgvector 컬럼(Vector(384))을 사용하는 레시피/식재료 추천(비동기).
#     - method="recipe":
#         1) MariaDB: 제목 부분/정확 일치 우선(RANK_TYPE=0, 인기순)
#         2) PostgreSQL: pgvector <-> 연산으로 부족분 보완(RANK_TYPE=1, 거리 오름차순)
#         3) MariaDB: 상세 정보 조인 + 재료 붙이기
#     - method="ingredient":
#         입력 재료(쉼표 구분)를 모두 포함하는 레시피를 MariaDB에서 조회 (유사도 없음)
#     - 반환: 상세 정보가 포함된 DataFrame (No. 컬럼 포함)
#     """
#     if method not in {"recipe", "ingredient"}:
#         raise ValueError("method must be 'recipe' or 'ingredient'")

#     # ========================== method: ingredient ==========================
#     if method == "ingredient":
#         ingredients = [i.strip() for i in query.split(",") if i.strip()]
#         if not ingredients:
#             return pd.DataFrame()

#         from sqlalchemy import func as sa_func
#         ids_stmt = (
#             select(Material.recipe_id)
#             .where(Material.material_name.in_(ingredients))
#             .group_by(Material.recipe_id)
#             .having(sa_func.count(sa_func.distinct(Material.material_name)) == len(ingredients))
#         )
#         ids_rows = await mariadb.execute(ids_stmt)
#         result_ids = [rid for (rid,) in ids_rows.all()]
#         if not result_ids:
#             return pd.DataFrame()

#         # 상세
#         name_col = getattr(Recipe, "cooking_name", None) or getattr(Recipe, "recipe_title")
#         detail_stmt = (
#             select(
#                 Recipe.recipe_id.label("RECIPE_ID"),
#                 name_col.label("RECIPE_TITLE"),
#                 Recipe.scrap_count.label("SCRAP_COUNT"),
#                 Recipe.cooking_case_name.label("COOKING_CASE_NAME"),
#                 Recipe.cooking_category_name.label("COOKING_CATEGORY_NAME"),
#                 Recipe.cooking_introduction.label("COOKING_INTRODUCTION"),
#                 Recipe.number_of_serving.label("NUMBER_OF_SERVING"),
#                 Recipe.thumbnail_url.label("THUMBNAIL_URL"),
#             )
#             .where(Recipe.recipe_id.in_(result_ids))
#             .order_by(desc(Recipe.scrap_count))
#         )
#         detail_rows = (await mariadb.execute(detail_stmt)).all()
#         final_df = pd.DataFrame(detail_rows, columns=[
#             "RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
#             "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
#         ])

#         # 번호 컬럼
#         final_df.insert(0, "No.", range(1, len(final_df) + 1))

#         # 재료 붙이기
#         m_stmt = select(
#             Material.recipe_id, Material.material_name, Material.measure_amount, Material.measure_unit
#         ).where(Material.recipe_id.in_(result_ids))
#         m_rows = (await mariadb.execute(m_stmt)).all()
#         if m_rows:
#             m_df = pd.DataFrame(m_rows, columns=["RECIPE_ID","MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"])
#             final_df = final_df.merge(m_df, on="RECIPE_ID", how="left")

#         return final_df

#     # ============================ method: recipe ============================
#     # 1) 제목 부분/정확 일치(인기순)
#     name_col = getattr(Recipe, "cooking_name", None) or getattr(Recipe, "recipe_title")
#     base_stmt = (
#         select(Recipe.recipe_id, name_col.label("RECIPE_TITLE"))
#         .where(name_col.contains(query))
#         .order_by(desc(Recipe.scrap_count))
#         .limit(top_k)
#     )
#     base_rows = (await mariadb.execute(base_stmt)).all()
#     exact_df = pd.DataFrame(base_rows, columns=["RECIPE_ID","RECIPE_TITLE"])
#     exact_df["RANK_TYPE"] = 0

#     exact_k = min(len(exact_df), top_k)
#     exact_df = exact_df.head(exact_k)
#     seen_ids = [int(x) for x in exact_df["RECIPE_ID"].tolist()]
#     remaining_k = top_k - exact_k

#     # 2) pgvector <-> 보완 — 포트 호출
#     similar_df = pd.DataFrame(columns=["RECIPE_ID","SIMILARITY","RANK_TYPE"])
#     if remaining_k > 0:
#         pairs = await vector_searcher.find_similar_ids(
#             pg_db=postgres,
#             query=query,
#             top_k=remaining_k,
#             exclude_ids=seen_ids or None,
#         )
#         if pairs:
#             tmp = pd.DataFrame(pairs, columns=["RECIPE_ID","DISTANCE"])
#             tmp["SIMILARITY"] = -tmp["DISTANCE"]
#             tmp["RANK_TYPE"] = 1
#             similar_df = tmp[["RECIPE_ID","SIMILARITY","RANK_TYPE"]]

#     # 3) 합치기
#     final_base = pd.concat([exact_df[["RECIPE_ID","RANK_TYPE"]], similar_df[["RECIPE_ID","RANK_TYPE"]]], ignore_index=True)
#     if final_base.empty:
#         return pd.DataFrame()
#     final_base = final_base.drop_duplicates(subset=["RECIPE_ID"]).sort_values(by="RANK_TYPE").reset_index(drop=True)

#     # 4) 상세 조인
#     ids = [int(x) for x in final_base["RECIPE_ID"].tolist()]
#     detail_stmt = (
#         select(
#             Recipe.recipe_id.label("RECIPE_ID"),
#             name_col.label("RECIPE_TITLE"),
#             Recipe.scrap_count.label("SCRAP_COUNT"),
#             Recipe.cooking_case_name.label("COOKING_CASE_NAME"),
#             Recipe.cooking_category_name.label("COOKING_CATEGORY_NAME"),
#             Recipe.cooking_introduction.label("COOKING_INTRODUCTION"),
#             Recipe.number_of_serving.label("NUMBER_OF_SERVING"),
#             Recipe.thumbnail_url.label("THUMBNAIL_URL"),
#         )
#         .where(Recipe.recipe_id.in_(ids))
#     )
#     detail_rows = (await mariadb.execute(detail_stmt)).all()
#     detail_df = pd.DataFrame(detail_rows, columns=[
#         "RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
#         "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
#     ])

#     final_df = final_base.merge(detail_df, on="RECIPE_ID", how="left")
#     final_df.insert(0, "No.", range(1, len(final_df) + 1))

#     # 5) 재료 붙이기 (필요시)
#     if ids:
#         m_stmt = select(Material.recipe_id, Material.material_name, Material.measure_amount, Material.measure_unit)\
#                     .where(Material.recipe_id.in_(ids))
#         m_rows = (await mariadb.execute(m_stmt)).all()
#         if m_rows:
#             m_df = pd.DataFrame(m_rows, columns=["RECIPE_ID","MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"])
#             final_df = final_df.merge(m_df, on="RECIPE_ID", how="left")

#     return final_df


async def get_recipe_rating(db: AsyncSession, recipe_id: int) -> float:
    """
    해당 레시피의 별점 평균값을 반환
    """
    stmt = (
        select(func.avg(RecipeRating.rating)).where(RecipeRating.recipe_id == recipe_id)  # type: ignore
    )
    avg_rating = (await db.execute(stmt)).scalar()
    return float(avg_rating) if avg_rating is not None else 0.0


async def set_recipe_rating(db: AsyncSession, recipe_id: int, user_id: int, rating: int) -> int:
    """
    새로운 별점을 등록(0~5 int)하고 저장된 값을 반환
    """
    new_rating = RecipeRating(recipe_id=recipe_id, user_id=user_id, rating=rating)
    db.add(new_rating)
    return rating


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
    from sqlalchemy import text
    
    # logger.info(f"레시피 식재료 상태 조회 시작: recipe_id={recipe_id}, user_id={user_id}")
    
    # 최적화된 쿼리: 레시피 재료와 주문/장바구니 정보를 한 번에 조회
    sql_query = """
    WITH recipe_materials AS (
        SELECT material_name
        FROM MATERIAL
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
        INNER JOIN HOMESHOPPING_ORDER ho ON o.order_id = ho.order_id
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


async def get_homeshopping_products_by_ingredient(
    db: AsyncSession, 
    ingredient: str
) -> List[Dict]:
    """
    홈쇼핑 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
    - 상품 이미지, 상품명, 브랜드명, 가격 포함
    """
    # logger.info(f"홈쇼핑 상품 검색 시작: ingredient={ingredient}")
    
    try:
        stmt = (
            select(
                HomeshoppingList.product_id,
                HomeshoppingList.product_name,
                HomeshoppingList.thumb_img_url,
                HomeshoppingProductInfo.dc_price,
                HomeshoppingProductInfo.sale_price
            )
            .join(
                HomeshoppingProductInfo, 
                HomeshoppingList.product_id == HomeshoppingProductInfo.product_id
            )
            .where(HomeshoppingList.product_name.contains(ingredient))
            .order_by(HomeshoppingList.product_name)
        )
        
        result = await db.execute(stmt)
        products = result.all()
        
        # 결과를 딕셔너리 리스트로 변환
        product_list = []
        for product in products:
            product_dict = {
                "product_id": product.product_id,
                "product_name": product.product_name,
                "brand_name": None,  # 홈쇼핑 모델에 브랜드명 필드가 없음
                "price": product.dc_price or product.sale_price or 0,
                "thumb_img_url": product.thumb_img_url
            }
            product_list.append(product_dict)
        
    # logger.info(f"홈쇼핑 상품 검색 완료: ingredient={ingredient}, 상품 개수={len(product_list)}")
        return product_list
        
    except Exception as e:
        logger.error(f"홈쇼핑 상품 검색 실패: ingredient={ingredient}, error={e}")
        return []


async def get_recipe_ingredients_status(
    db: AsyncSession, 
    user_id: int, 
    recipe_id: int
) -> Optional[Dict]:
    """
    레시피의 식재료별 사용자 보유/장바구니/미보유 상태 조회 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        recipe_id: 레시피 ID
        
    Returns:
        식재료 상태 정보 딕셔너리
    """
    from sqlalchemy import text
    
    # logger.info(f"레시피 식재료 상태 조회 시작: user_id={user_id}, recipe_id={recipe_id}")
    
    try:
        # 최적화된 쿼리: 레시피 재료와 주문/장바구니 정보를 한 번에 조회
        sql_query = """
        WITH recipe_materials AS (
            SELECT material_name
            FROM MATERIAL
            WHERE recipe_id = :recipe_id
        ),
        recent_orders AS (
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
            INNER JOIN HOMESHOPPING_ORDER ho ON o.order_id = ho.order_id
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
        )
        SELECT 
            rm.material_name,
            ro.order_id,
            ro.order_time,
            ro.kok_product_name,
            ro.quantity as order_quantity,
            ro.order_type,
            ci.kok_cart_id,
            ci.kok_quantity as cart_quantity,
            ci.cart_type
        FROM recipe_materials rm
        LEFT JOIN recent_orders ro ON rm.material_name = ro.kok_product_name
        LEFT JOIN cart_items ci ON rm.material_name = ci.kok_product_name
        ORDER BY rm.material_name
        """
        
        result = await db.execute(text(sql_query), {
            "recipe_id": recipe_id,
            "user_id": user_id
        })
        rows = result.fetchall()
        
        if not rows:
            logger.warning(f"레시피를 찾을 수 없음: recipe_id={recipe_id}")
            return None
        
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
                    "order_date": row.order_time,
                    "order_type": row.order_type,
                    "product_name": row.kok_product_name,
                    "quantity": row.order_quantity,
                    "match_score": 1.0  # 정확한 매치
                })
            
            # 장바구니 정보가 있는 경우 (장바구니 상태)
            if row.kok_cart_id:
                material_status[material_name]["cart"].append({
                    "cart_id": row.kok_cart_id,
                    "cart_type": row.cart_type,
                    "product_name": row.kok_product_name,
                    "quantity": row.cart_quantity,
                    "match_score": 1.0  # 정확한 매치
                })
        
        # 최종 상태 판별
        ingredients_status = []
        owned_count = 0
        cart_count = 0
        not_owned_count = 0
        
        for material_name, status in material_status.items():
            order_info = None
            cart_info = None
            status_type = "not_owned"
            
            # 보유 상태 확인
            if status["owned"]:
                status_type = "owned"
                order_info = status["owned"][0]  # 첫 번째 주문 정보 사용
                owned_count += 1
            # 장바구니 상태 확인 (보유가 아닌 경우에만)
            elif status["cart"]:
                status_type = "cart"
                cart_info = status["cart"][0]  # 첫 번째 장바구니 정보 사용
                cart_count += 1
            else:
                not_owned_count += 1
            
            # 재료 상태 정보 추가
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



