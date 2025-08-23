"""
레시피/재료/별점 DB 접근(CRUD) 함수
- 모든 recipe_url 생성은 get_recipe_url 함수로 일원화
- 중복 dict 변환 등 최소화
- 추천/유사도 계산은 services.recommend의 포트(RecommenderPort)에 위임
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, text
from typing import List, Optional, Dict, Tuple
import pandas as pd
import copy
from datetime import datetime, timedelta

from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder
from services.kok.models.kok_model import KokProductInfo

from services.recipe.models.recipe_model import (
    Recipe, Material, RecipeRating, RecipeVector
)
from services.homeshopping.models.homeshopping_model import (
    HomeshoppingList, HomeshoppingProductInfo, HomeshoppingImgUrl
)

# ⬇️ 추가: 추천 포트(로컬/원격 어댑터)는 라우터/서비스에서 DI로 주입하여 사용
from services.recommend.ports import VectorSearcherPort

# ⬇️ 추가: 추천 관련 유틸리티 함수들
from ..utils.recommendation_utils import (
    get_recipe_url,
    recommend_sequentially_for_inventory
)

from common.logger import get_logger

# 로거 초기화
logger = get_logger("recipe_crud")


async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> Optional[Dict]:
    """
    레시피 상세정보(+재료 리스트, recipe_url 포함) 반환
    """
    logger.info(f"레시피 상세정보 조회 시작: recipe_id={recipe_id}")
    
    stmt = select(Recipe).where(Recipe.recipe_id == recipe_id)  # type: ignore
    recipe_row = await db.execute(stmt)
    recipe = recipe_row.scalar_one_or_none()
    if not recipe:
        logger.warning(f"레시피를 찾을 수 없음: recipe_id={recipe_id}")
        return None

    mats_row = await db.execute(select(Material).where(Material.recipe_id == recipe_id))  # type: ignore
    materials = [m.__dict__ for m in mats_row.scalars().all()]
    recipe_url = get_recipe_url(recipe_id)
    result_dict = {**recipe.__dict__, "materials": materials, "recipe_url": recipe_url}
    
    logger.info(f"레시피 상세정보 조회 완료: recipe_id={recipe_id}, 재료 개수={len(materials)}")
    return result_dict


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
    logger.info(f"재료 기반 레시피 추천 시작: 재료={ingredients}, 분량={amounts}, 단위={units}, 페이지={page}, 크기={size}")
    
    # 기본 쿼리 (인기순)
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id)  # type: ignore
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))
    )
    
    # 순차적 재고 소진 알고리즘 적용
    logger.info("순차적 재고 소진 알고리즘 모드")
    
    return await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )

async def recommend_recipes_combination_1(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10
) -> Tuple[List[Dict], int]:
    """
    1조합: 전체 레시피 풀에서 가장 많은 재료 사용하는 순으로 선택
    """
    logger.info(f"1조합 레시피 추천 시작: 재료={ingredients}, 분량={amounts}, 단위={units}")
    
    # 전체 레시피 풀 사용 (인기순 정렬)
    base_stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id)
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))  # 인기순 정렬
    )
    
    return await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )

async def recommend_recipes_combination_2(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10,
    exclude_recipe_ids: List[int] = None
) -> Tuple[List[Dict], int]:
    """
    2조합: 1조합에서 사용된 레시피를 제외한 나머지 레시피 풀에서 선택
    """
    logger.info(f"2조합 레시피 추천 시작: 재료={ingredients}, 제외할 레시피={exclude_recipe_ids}")
    
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
        logger.info(f"제외할 레시피 ID: {exclude_recipe_ids}")
    
    return await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )

async def recommend_recipes_combination_3(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[float]] = None,
    units: Optional[List[str]] = None,
    page: int = 1,
    size: int = 10,
    exclude_recipe_ids: List[int] = None
) -> Tuple[List[Dict], int]:
    """
    3조합: 1조합, 2조합에서 사용된 레시피를 제외한 나머지 레시피 풀에서 선택
    """
    logger.info(f"3조합 레시피 추천 시작: 재료={ingredients}, 제외할 레시피={exclude_recipe_ids}")
    
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
        logger.info(f"제외할 레시피 ID: {exclude_recipe_ids}")
    
    return await execute_standard_inventory_algorithm(
        db, base_stmt, ingredients, amounts, units, page, size
    )

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
    logger.info(f"표준 재고 소진 알고리즘 실행: 페이지={page}, 크기={size}")
    
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
    logger.info("전체 후보 레시피 조회 시작")
    candidate_recipes = (await db.execute(base_stmt)).scalars().unique().all()
    logger.info(f"전체 후보 레시피 개수: {len(candidate_recipes)}")
    
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
        logger.info(f"DataFrame 생성 완료: {len(recipe_df)}행")
    except Exception as e:
        logger.error(f"DataFrame 생성 실패: {e}")
        return [], 0
    
    # 2-5. 순차적 재고 소진 알고리즘 실행 (요청 페이지의 끝까지 생성하면 조기 중단)
    max_results_needed = page * size
    logger.info(f"알고리즘 실행: 최대 {max_results_needed}개까지 생성")
    
    recommended, remaining_stock, early_stopped = recommend_sequentially_for_inventory(
        initial_ingredients,
        recipe_material_map,
        recipe_df,
        max_results=max_results_needed
    )
    
    logger.info(f"알고리즘 완료: {len(recommended)}개 생성, 조기중단: {early_stopped}")
    
    # 2-6. 페이지네이션 적용
    start, end = (page-1)*size, (page-1)*size + size
    paginated_recommended = recommended[start:end]
    
    # 2-7. 전체 개수 계산
    if early_stopped:
        # 조기중단이면 정확한 total 계산이 어려우므로 근사값 반환
        approx_total = (page - 1) * size + len(paginated_recommended) + 1
        logger.info(f"조기중단으로 인한 근사 total: {approx_total}")
        return paginated_recommended, approx_total
    else:
        total = len(recommended)
        logger.info(f"정확한 total: {total}")
        return paginated_recommended, total


# recommend_sequentially_for_inventory 함수는 utils/recommendation_utils.py로 이동됨


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

    # ========================== method: ingredient ==========================
    if method == "ingredient":
        ingredients = [i.strip() for i in (query or "").split(",") if i.strip()]
        if not ingredients:
            return pd.DataFrame()

        # AND 포함(모든 재료 포함) — 기존 로직 유지
        from sqlalchemy import func as sa_func
        ids_stmt = (
            select(Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Material.recipe_id)
            .having(sa_func.count(sa_func.distinct(Material.material_name)) == len(ingredients))
        )
        ids_rows = await mariadb.execute(ids_stmt)
        all_ids = [int(rid) for (rid,) in ids_rows.all()]
        if not all_ids:
            return pd.DataFrame()

        # 페이지 슬라이스
        start = (page - 1) * size
        page_ids = all_ids[start : start + size]
        if not page_ids:
            return pd.DataFrame()

        name_col = getattr(Recipe, "cooking_name", None) or getattr(Recipe, "recipe_title")
        detail_stmt = (
            select(
                Recipe.recipe_id.label("RECIPE_ID"),
                name_col.label("RECIPE_TITLE"),
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
            "RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
            "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
        ])

        # 페이지 순서 유지
        order_map = {rid: i for i, rid in enumerate(page_ids)}
        final_df["__order__"] = final_df["RECIPE_ID"].map(order_map).fillna(10**9)
        final_df = final_df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)

        # 번호 컬럼(페이지 기준)
        final_df.insert(0, "No.", range(1, len(final_df) + 1))

        # (옵션) 재료 집계
        if include_materials and page_ids:
            m_stmt = select(
                Material.recipe_id, Material.material_name, Material.measure_amount, Material.measure_unit
            ).where(Material.recipe_id.in_(page_ids))
            m_rows = (await mariadb.execute(m_stmt)).all()
            if m_rows:
                m_df = pd.DataFrame(m_rows, columns=["RECIPE_ID","MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"])
                # 레시피당 리스트로 집계
                mats = (
                    m_df.groupby("RECIPE_ID")[["MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"]]
                    .apply(lambda g: g.to_dict("records"))
                    .rename("MATERIALS")
                    .reset_index()
                )
                final_df = final_df.merge(mats, on="RECIPE_ID", how="left")

        return final_df

    # ============================ method: recipe ============================
    # 1) 제목 부분/정확 일치(인기순) — 현재 페이지까지 필요한 개수만 수집
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

    exact_ids = [int(x) for x in exact_df["RECIPE_ID"].tolist()]
    need_after_exact = max(0, fetch_upto - len(exact_ids))

    # 2) pgvector <-> 보완 — 포트 호출(여유분을 더 모아 중복 여지 대비)
    vec_ids: List[int] = []
    if need_after_exact > 0:
        pairs = await vector_searcher.find_similar_ids(
            pg_db=postgres,
            query=query,
            top_k=need_after_exact + size * 2,  # 버퍼
            exclude_ids=exact_ids or None,
        )
        vec_ids = [rid for rid, _ in pairs]

    # 3) ID 병합 → 중복 제거 → 페이지 슬라이스
    merged_ids: List[int] = []
    seen = set()
    for rid in exact_ids + vec_ids:
        if rid not in seen:
            merged_ids.append(rid)
            seen.add(rid)

    start = (page - 1) * size
    page_ids = merged_ids[start : start + size]
    if not page_ids:
        return pd.DataFrame()

    # 4) 상세 조인(해당 페이지 ID만)
    detail_stmt = (
        select(
            Recipe.recipe_id.label("RECIPE_ID"),
            name_col.label("RECIPE_TITLE"),
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
        "RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
        "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
    ])

    # 5) RANK_TYPE 부여(제목일치=0, 유사도=1) + 순서 유지 + 번호
    exact_set = set(exact_ids)
    detail_df["RANK_TYPE"] = detail_df["RECIPE_ID"].apply(lambda x: 0 if int(x) in exact_set else 1)

    order_map = {rid: i for i, rid in enumerate(page_ids)}
    detail_df["__order__"] = detail_df["RECIPE_ID"].map(order_map).fillna(10**9)
    final_df = detail_df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)
    final_df.insert(0, "No.", range(1, len(final_df) + 1))

    # 6) (옵션) 재료 집계 — 레시피당 1행 유지
    if include_materials and page_ids:
        m_stmt = select(
            Material.recipe_id, Material.material_name, Material.measure_amount, Material.measure_unit
        ).where(Material.recipe_id.in_(page_ids))
        m_rows = (await mariadb.execute(m_stmt)).all()
        if m_rows:
            m_df = pd.DataFrame(m_rows, columns=["RECIPE_ID","MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"])
            mats = (
                m_df.groupby("RECIPE_ID")[["MATERIAL_NAME","MEASURE_AMOUNT","MEASURE_UNIT"]]
                .apply(lambda g: g.to_dict("records"))
                .rename("MATERIALS")
                .reset_index()
            )
            final_df = final_df.merge(mats, on="RECIPE_ID", how="left")

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
    await db.commit()
    return rating


async def fetch_recipe_ingredients_status(
    db: AsyncSession, 
    recipe_id: int, 
    user_id: int
) -> Dict:
    """
    레시피의 식재료 상태 조회 (보유/장바구니/미보유)
    - 보유: 최근 7일 내 주문한 상품 / 재고 소진에 입력한 식재료
    - 장바구니: 현재 장바구니에 담긴 상품
    - 미보유: 레시피 식재료 중 보유/장바구니 상태를 제외한 식재료
    """
    logger.info(f"레시피 식재료 상태 조회 시작: recipe_id={recipe_id}, user_id={user_id}")
    
    # 1. 레시피의 모든 식재료 조회
    materials_stmt = select(Material).where(Material.recipe_id == recipe_id)
    materials_result = await db.execute(materials_stmt)
    materials = materials_result.scalars().all()
    
    if not materials:
        logger.warning(f"레시피 {recipe_id}의 식재료를 찾을 수 없음")
        return {
            "recipe_id": recipe_id,
            "user_id": user_id,
            "ingredients_status": {"owned": [], "cart": [], "not_owned": []},
            "summary": {"total_ingredients": len(materials), "owned_count": 0, "cart_count": 0, "not_owned_count": 0}
        }
    
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    # 콕 주문에서 최근 7일 내 주문 조회
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
        .where(Order.cancel_time.is_(None))  # 취소되지 않은 주문만
    )
    
    # 홈쇼핑 주문에서 최근 7일 내 주문 조회
    homeshopping_orders_stmt = (
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
        .where(Order.cancel_time.is_(None))  # 취소되지 않은 주문만
    )
    
    try:
        # 콕 주문 조회
        kok_orders_result = await db.execute(kok_orders_stmt)
        kok_orders = kok_orders_result.all()
        
        # 홈쇼핑 주문 조회
        homeshopping_orders_result = await db.execute(homeshopping_orders_stmt)
        homeshopping_orders = homeshopping_orders_result.all()
        
        # 주문한 상품명으로 보유 재료 구성
        owned_materials = []
        
        # 콕 주문 처리
        for order_id, order_time, kok_order_id, product_name in kok_orders:
            owned_materials.append({
                "material_name": product_name,
                "order_date": order_time,
                "order_id": order_id,
                "order_type": "kok"
            })
        
        # 홈쇼핑 주문 처리
        for order_id, order_time, homeshopping_order_id, product_name in homeshopping_orders:
            owned_materials.append({
                "material_name": product_name,
                "order_date": order_time,
                "order_id": order_id,
                "order_type": "homeshopping"
            })
            
    except Exception as e:
        logger.warning(f"주문 정보 조회 실패, 빈 리스트로 처리: {e}")
        owned_materials = []
    
    # 3. 장바구니에 담긴 상품 조회 (장바구니 상태)
    # 장바구니 테이블이 있다면 여기서 조회
    # 현재는 빈 리스트로 처리 (장바구니 테이블이 구현되면 수정 필요)
    cart_materials = []
    
    # 4. 레시피 재료와 주문 상품 매칭하여 실제 보유 재료만 필터링
    all_material_names = {m.material_name for m in materials}
    
    # 레시피 재료와 매칭되는 주문 상품만 필터링
    matched_owned_materials = []
    for material in owned_materials:
        # 주문한 상품명이 레시피 재료명과 정확히 일치하거나 포함되는지 확인
        if any(material["material_name"] in recipe_material or recipe_material in material["material_name"] 
               for recipe_material in all_material_names):
            matched_owned_materials.append(material)
    
    # 실제 보유 재료명 집합
    owned_material_names = {m["material_name"] for m in matched_owned_materials}
    cart_material_names = {m["material_name"] for m in cart_materials}
    
    not_owned_materials = [
        {"material_name": name}
        for name in all_material_names 
        if name not in owned_material_names and name not in cart_material_names
    ]
    
    # 5. 결과 구성
    ingredients_status = {
        "owned": matched_owned_materials,
        "cart": cart_materials,
        "not_owned": not_owned_materials
    }
    
    summary = {
        "total_ingredients": len(materials),
        "owned_count": len(matched_owned_materials),
        "cart_count": len(cart_materials),
        "not_owned_count": len(not_owned_materials)
    }
    
    result = {
        "recipe_id": recipe_id,
        "user_id": user_id,
        "ingredients_status": ingredients_status,
        "summary": summary
    }
    
    logger.info(f"레시피 식재료 상태 조회 완료: {summary}")
    return result


async def get_homeshopping_products_by_ingredient(
    db: AsyncSession, 
    ingredient: str
) -> List[Dict]:
    """
    홈쇼핑 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
    - 상품 이미지, 상품명, 브랜드명, 가격 포함
    """
    logger.info(f"홈쇼핑 상품 검색 시작: ingredient={ingredient}")
    
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
                "image_url": product.thumb_img_url
            }
            product_list.append(product_dict)
        
        logger.info(f"홈쇼핑 상품 검색 완료: ingredient={ingredient}, 상품 개수={len(product_list)}")
        return product_list
        
    except Exception as e:
        logger.error(f"홈쇼핑 상품 검색 실패: ingredient={ingredient}, error={e}")
        return []
