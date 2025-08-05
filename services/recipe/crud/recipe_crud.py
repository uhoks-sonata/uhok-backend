"""
레시피/재료/별점 DB 접근(CRUD) 함수
- 모든 recipe_url 생성은 get_recipe_url 함수로 일원화
- 중복 dict 변환 등 최소화
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional, Dict, Tuple

from services.recipe.models.recipe_model import Recipe, Material, RecipeRating
# 함수 이름 수정 필요 ( 아직 미정의 )
from services.recommend.team_recommend_model import find_similar_recipes

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


async def search_recipes_by_keyword(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    size: int = 5
) -> Tuple[List[dict], int]:
    """
    레시피명(키워드) 기반 유사 레시피 추천 (모델 결과 기반, 페이지네이션 지원)
    """
    # 1. 유사도 모델에서 추천받은 recipe_id 리스트 (입력순서)
    similar_ids = find_similar_recipes(keyword, n=1000)  # 최대 1000개 등 제한 가능
    if not similar_ids:
        return [], 0

    # 2. 추천된 recipe_id로 상세 DB 조회
    stmt = select(Recipe).where(Recipe.recipe_id.in_(similar_ids))
    result = await db.execute(stmt)
    recipes = result.scalars().all()
    recipe_map = {r.recipe_id: r for r in recipes}

    # 3. 입력 순서/추천 순서 보장 & 페이지네이션 적용
    result_list = [
        {
            **recipe_map[recipe_id].__dict__,
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