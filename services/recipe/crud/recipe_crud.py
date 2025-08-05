"""
레시피/재료/별점 DB 접근(CRUD) 함수
- 모든 recipe_url 생성은 get_recipe_url 함수로 일원화
- 중복 dict 변환 등 최소화
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional, Dict, Tuple
import pandas as pd

from services.recipe.models.recipe_model import Recipe, Material, RecipeRating
from services.recommend.recommend_service import _get_recipe_recommendations

def get_recipe_url(recipe_id: int) -> str:
    """
    만개의 레시피 상세페이지 URL 동적 생성
    """
    return f"https://www.10000recipe.com/recipe/{recipe_id}"


async def get_recipe_detail(db: AsyncSession, recipe_id: int) -> Optional[Dict]:
    """
    레시피 상세정보(+재료 리스트, recipe_url 포함) 반환
    """
    stmt = select(Recipe).where(Recipe.recipe_id == recipe_id) # type: ignore
    recipe_row = await db.execute(stmt)
    recipe = recipe_row.scalar_one_or_none()
    if not recipe:
        return None

    mats_row = await db.execute(select(Material).where(Material.recipe_id == recipe_id)) # type: ignore
    materials = [m.__dict__ for m in mats_row.scalars().all()]
    recipe_url = get_recipe_url(recipe_id)
    result_dict = {**recipe.__dict__, "materials": materials, "recipe_url": recipe_url}
    return result_dict


async def recommend_recipes_by_ingredients(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[str]] = None,
    units: Optional[List[str]] = None,
    consume_count: Optional[int] = None,
    page: int = 1,
    size: int = 5
) -> Tuple[List[Dict], int]:
    """
    - 페이지네이션(page, size)과 전체 개수(total) 반환
    - matched_ingredient_count(입력 재료 중 실제로 들어간 개수) 포함
    """

    # 1. 입력 재료 중 하나 이상을 포함하는 레시피 후보 전체 추출(인기순)
    stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id) # type: ignore
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(Recipe.scrap_count))
    )
    result = await db.execute(stmt)
    candidate_recipes = result.scalars().all()
    total = len(candidate_recipes)  # 전체 후보 개수

    # 2. 레시피별 실제 들어간 재료(Material) 리스트 미리 조회(map 저장, 최적화)
    recipe_materials_map = {}
    for recipe in candidate_recipes:
        mats_stmt = select(Material).where(Material.recipe_id == recipe.recipe_id) # type: ignore
        mats = (await db.execute(mats_stmt)).scalars().all()
        recipe_materials_map[recipe.recipe_id] = mats

    # 3. 입력한 재료가 실제로 들어간 개수 반환 함수
    def get_matched_count(recipe_id):
        mats = recipe_materials_map[recipe_id]
        return len(set(ingredients) & {m.material_name for m in mats})

    # 4. case2: 소진조건 미입력 → 단순 재료 포함 레시피 반환
    if not amounts or not units or not consume_count:
        filtered = [
            {
                **r.__dict__,
                "recipe_url": get_recipe_url(r.recipe_id),
                "matched_ingredient_count": get_matched_count(r.recipe_id),
            }
            for r in candidate_recipes
        ]
        # 페이지네이션
        start, end = (page-1)*size, (page-1)*size + size
        return filtered[start:end], total

    # 5. case1: amounts, units, consume_count 모두 있을 때 소진조건 체크
    usable_total = {
        (ingredients[i], units[i]): float(amounts[i]) * consume_count
        for i in range(len(ingredients))
    }
    filtered = []
    for recipe in candidate_recipes:
        mats = recipe_materials_map[recipe.recipe_id]
        ok = True
        for m in mats:
            key = (m.material_name, m.measure_unit)
            if key in usable_total:
                try:
                    recipe_required = float(m.measure_amount) if m.measure_amount else 0
                except Exception:
                    recipe_required = 0
                if recipe_required > usable_total[key]:
                    ok = False
                    break
        if ok:
            filtered.append({
                **recipe.__dict__,
                "recipe_url": get_recipe_url(recipe.recipe_id),
                "matched_ingredient_count": get_matched_count(recipe.recipe_id),
            })
        if len(filtered) >= (page * size):  # 성능 최적화: 필요한 개수만 필터링
            break
    # 페이지네이션
    start, end = (page-1)*size, (page-1)*size + size
    return filtered[start:end], len(filtered)


async def search_recipes_by_keyword_postgres(
    db: AsyncSession,   # 반드시 get_postgres_recommend_db로 주입!
    keyword: str,
    page: int = 1,
    size: int = 5
) -> Tuple[List[dict], int]:
    """
    [PostgreSQL REC_DB] 레시피명(키워드) 기반 유사 레시피 추천 (페이지네이션 지원)
    """
    # 1. 추천DB에서 전체 벡터 정보 불러오기 (Postgres 전용 테이블)
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT RECIPE_ID, COOKING_NAME, VECTOR_NAME FROM REC_RECIPE WHERE VECTOR_NAME IS NOT NULL")
    )
    rows = result.fetchall()
    df = pd.DataFrame(rows, columns=["RECIPE_ID", "COOKING_NAME", "VECTOR_NAME"])

    # 2. 유사도 기반 추천
    sim_df = await _get_recipe_recommendations(df, keyword, top_k=1000)
    similar_ids = sim_df["RECIPE_ID"].astype(int).tolist()
    if not similar_ids:
        return [], 0

    # 3. 상세 조회 (PostgreSQL의 REC_RECIPE, 혹은 정규화된 테이블 사용)
    stmt = text(f"SELECT * FROM REC_RECIPE WHERE RECIPE_ID = ANY(:ids)")
    result = await db.execute(stmt, {"ids": similar_ids})
    recipes = result.fetchall()
    recipe_map = {r[0]: dict(zip(result.keys(), r)) for r in recipes}

    # 4. 추천 순서/페이지네이션 적용
    result_list = [
        {
            **recipe_map[recipe_id],
            "recipe_url": get_recipe_url(recipe_id)
        }
        for recipe_id in similar_ids if recipe_id in recipe_map
    ]
    total = len(result_list)
    start, end = (page-1)*size, (page-1)*size + size
    paginated = result_list[start:end]
    return paginated, total


async def get_recipe_rating(db: AsyncSession, recipe_id: int) -> float:
    """
    해당 레시피의 별점 평균값을 반환
    """
    stmt = select(func.avg(RecipeRating.rating)).where(RecipeRating.recipe_id == recipe_id) # type: ignore
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


###########################################################
# async def get_recipe_comments(
#         db: AsyncSession,
#         recipe_id: int,
#         page: int,
#         size: int
# ) -> Tuple[List[dict], int]:
#     """
#         주어진 레시피의 후기 목록(페이지네이션)과 총 개수를 반환
#     """
#     offset = (page - 1) * size
#     stmt = (
#         select(RecipeComment)
#         .where(RecipeComment.recipe_id == recipe_id) # type: ignore
#         .offset(offset)
#         .limit(size)
#     )
#     comments = (await db.execute(stmt)).scalars().all()
#     count_stmt = (
#         select(func.count()).where(RecipeComment.recipe_id == recipe_id) # type: ignore
#     )
#     total = (await db.execute(count_stmt)).scalar()
#     return [c.__dict__ for c in comments], total
#
# async def add_recipe_comment(
#         db: AsyncSession,
#         recipe_id: int,
#         user_id: int,
#         comment: str
# ) -> dict:
#     """
#         새로운 후기(코멘트)를 등록하고 저장된 내용을 반환
#     """
#     new_comment = RecipeComment(recipe_id=recipe_id, user_id=user_id, comment=comment)
#     db.add(new_comment)
#     await db.commit()
#     await db.refresh(new_comment)
#     return new_comment.__dict__