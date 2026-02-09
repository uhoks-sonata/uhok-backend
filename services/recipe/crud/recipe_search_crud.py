"""Recipe search and vector-backed recommendation CRUD functions."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.recipe.models.core_model import Material, Recipe
from services.recipe.utils.ports import VectorSearcherPort

logger = get_logger("recipe_crud")

async def search_recipes_with_pagination(
    *,
    mariadb: AsyncSession,
    method: str,
    recipe: str,
    page: int,
    size: int,
    result_ids: Optional[List[int]] = None,
) -> Tuple[pd.DataFrame, int, bool]:
    """
    레시피 검색(키워드/재료) 결과를 DataFrame으로 반환하고 페이지 정보도 함께 제공.
    - method="recipe": ML 검색 결과로 받은 result_ids 순서를 유지해 상세 조회
    - method="ingredient": 입력 재료를 모두 포함하는 레시피를 DB에서 조회
    반환: (page_df, total_approx, has_more)
    """
    if method == "recipe":
        if not result_ids:
            return pd.DataFrame(), 0, False

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
            .where(Recipe.recipe_id.in_(result_ids))
        )
        detail_rows = (await mariadb.execute(detail_stmt)).all()
        df = pd.DataFrame(detail_rows, columns=[
            "RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
            "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
        ])

        order_map = {rid: i for i, rid in enumerate(result_ids)}
        df["__order__"] = df["RECIPE_ID"].map(order_map)
        df = df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)

        has_more = len(df) > size
        start_index = (page - 1) * size
        page_df = df.iloc[:size] if not df.empty else df
        total_approx = start_index + len(page_df) + (1 if has_more else 0)
        return page_df, total_approx, has_more

    # method == "ingredient"
    ingredients = [i.strip() for i in (recipe or "").split(",") if i.strip()]
    if not ingredients:
        return pd.DataFrame(), 0, False

    total_stmt = (
        select(func.count(func.distinct(Material.recipe_id)))
        .where(Material.material_name.in_(ingredients))
        .having(func.count(func.distinct(Material.material_name)) == len(ingredients))
    )
    total_count = (await mariadb.execute(total_stmt)).scalar_one_or_none() or 0

    start_offset = (page - 1) * size
    ids_stmt = (
        select(Material.recipe_id)
        .where(Material.material_name.in_(ingredients))
        .group_by(Material.recipe_id)
        .having(func.count(func.distinct(Material.material_name)) == len(ingredients))
        .order_by(desc(func.count(func.distinct(Material.material_name))))
        .offset(start_offset).limit(size)
    )
    page_ids = (await mariadb.execute(ids_stmt)).scalars().all()

    if not page_ids:
        return pd.DataFrame(), total_count, total_count > page * size
    
    detail_stmt = select(Recipe).where(Recipe.recipe_id.in_(page_ids))
    detail_rows = (await mariadb.execute(detail_stmt)).scalars().all()
    df = pd.DataFrame([r.__dict__ for r in detail_rows])

    has_more = total_count > page * size
    return df, total_count, has_more


async def recommend_by_recipe_pgvector_v2(
    *,
    mariadb: AsyncSession,
    postgres: Optional[AsyncSession],
    query: str,
    method: str = "recipe",
    top_k: int = 25,
    vector_searcher: Optional[VectorSearcherPort] = None,
    page: int = 1,
    size: int = 10,
    include_materials: bool = False,
) -> pd.DataFrame:
    """
    벡터 검색 결과와 MariaDB 정보를 조합해 페이지 단위 레시피 목록을 반환한다.
    - method="recipe": 제목 검색 결과를 우선 사용하고 부족분은 vector_searcher 결과로 보완
    - method="ingredient": 입력 재료를 모두 포함하는 레시피를 DB에서 직접 조회
    """
    if method not in {"recipe", "ingredient"}:
        raise ValueError("method must be 'recipe' or 'ingredient'")

    page = max(1, int(page))
    size = max(1, int(size))
    fetch_upto = page * size

    # ========================== method: ingredient ==========================
    if method == "ingredient":
        ingredients = [i.strip() for i in (query or "").split(",") if i.strip()]
        if not ingredients:
            return pd.DataFrame()

        ids_stmt = (
            select(Material.recipe_id)
            .where(Material.material_name.in_(ingredients))
            .group_by(Material.recipe_id)
            .having(func.count(func.distinct(Material.material_name)) == len(ingredients))
            .order_by(desc(func.count(func.distinct(Material.material_name))))
        )
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
            "RECIPE_ID","RECIPE_TITLE","COOKING_NAME","SCRAP_COUNT","COOKING_CASE_NAME",
            "COOKING_CATEGORY_NAME","COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
        ])

        order_map = {rid: i for i, rid in enumerate(page_ids)}
        final_df["__order__"] = final_df["RECIPE_ID"].map(order_map).fillna(len(page_ids))
        final_df = final_df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)
        final_df.insert(0, "No.", range(1, len(final_df) + 1))

        if include_materials and page_ids:
            m_stmt = select(
                Material.recipe_id,
                Material.material_name,
                Material.measure_amount,
                Material.measure_unit
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

    # ============================ method: recipe ============================
    name_col = getattr(Recipe, "cooking_name", None) or getattr(Recipe, "recipe_title")
    base_stmt = (
        select(Recipe.recipe_id, name_col.label("RECIPE_TITLE"), Recipe.scrap_count)
        .where(name_col.contains(query))
        .order_by(desc(Recipe.scrap_count))
        .limit(max(fetch_upto, top_k))
    )
    base_rows = (await mariadb.execute(base_stmt)).all()
    exact_df = pd.DataFrame(base_rows, columns=["RECIPE_ID","RECIPE_TITLE","SCRAP_COUNT"]).drop_duplicates("RECIPE_ID")
    exact_ids = [int(x) for x in exact_df["RECIPE_ID"].tolist()]

    need_count = max(0, fetch_upto - len(exact_ids))
    buffer_size = max(size * 2, 10)
    vector_ids: List[int] = []
    if need_count > 0:
        if not vector_searcher:
            logger.warning("vector_searcher가 없어 제목 검색 결과만 반환합니다.")
        else:
            try:
                pairs = await vector_searcher.find_similar_ids(
                    pg_db=postgres,
                    query=query,
                    top_k=need_count + buffer_size,
                    exclude_ids=exact_ids or None,
                )
                vector_ids = [int(rid) for rid, _ in pairs]
            except Exception as e:
                logger.warning(f"벡터 검색 실패(query='{query[:20]}'): {e}")

    merged_ids: List[int] = []
    seen = set()
    for rid in exact_ids:
        if rid not in seen:
            merged_ids.append(rid)
            seen.add(rid)

    for rid in vector_ids:
        if rid not in seen:
            merged_ids.append(rid)
            seen.add(rid)
        if len(merged_ids) >= fetch_upto:
            break

    start = (page - 1) * size
    page_ids = merged_ids[start : start + size]
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
    detail_df = pd.DataFrame(detail_rows, columns=[
        "RECIPE_ID","RECIPE_TITLE","COOKING_NAME","SCRAP_COUNT","COOKING_CASE_NAME",
        "COOKING_CATEGORY_NAME","COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
    ])

    exact_set = set(exact_ids)
    detail_df["RANK_TYPE"] = detail_df["RECIPE_ID"].apply(lambda x: 0 if int(x) in exact_set else 1)
    order_map = {rid: i for i, rid in enumerate(page_ids)}
    detail_df["__order__"] = detail_df["RECIPE_ID"].map(order_map).fillna(len(page_ids))
    final_df = detail_df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)
    final_df.insert(0, "No.", range(1, len(final_df) + 1))

    if include_materials and page_ids:
        m_stmt = select(
            Material.recipe_id,
            Material.material_name,
            Material.measure_amount,
            Material.measure_unit
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
