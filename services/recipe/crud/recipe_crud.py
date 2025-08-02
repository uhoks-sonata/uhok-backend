"""
레시피 서비스 CRUD 함수 모음 (비동기, 주요 기능만)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from typing import List, Optional, Tuple

from services.recipe.models.recipe_model import Recipe, Material
from services.recipe.models.rating_model import Rating
from services.recipe.models.comment_model import Comment

# 1. 재료소진/레시피추천 목록 (by-ingredients)
async def get_recipes_by_ingredients(
    db: AsyncSession,
    ingredients: List[str],
    amounts: Optional[List[str]] = None,
    count: Optional[int] = None
) -> List[dict]:
    """
    입력 재료/분량/횟수로 레시피 10개 추천
    - amount/count 모두 생략 시 해당 재료 포함 상위 10개
    """
    # 간단 예시: 재료명 하나라도 포함하는 레시피
    # 실제 구현은 분량/횟수 로직까지 추가 필요
    stmt = (
        select(Recipe)
        .join(Material, Recipe.recipe_id == Material.recipe_id) # type: ignore
        .where(Material.material_name.in_(ingredients))
        .group_by(Recipe.recipe_id)
        .order_by(desc(func.count(Material.material_id)))
        .limit(10)
    )
    result = await db.execute(stmt)
    recipes = result.scalars().all()
    # matched_ingredient_count 계산 예시
    recipe_list = []
    for r in recipes:
        matched_count = sum(
            1 for m in r.materials if m.material_name in ingredients
        )
        recipe_list.append({
            **r.__dict__,
            "matched_ingredient_count": matched_count
        })
    return recipe_list


# 2. 레시피명 키워드 추천 (search)
async def search_recipes_by_keyword(
    db: AsyncSession,
    keyword: str
) -> List[dict]:
    """
    레시피명 키워드 기반 10개 추천
    """
    stmt = (
        select(Recipe)
        .where(Recipe.recipe_title.ilike(f"%{keyword}%"))
        .order_by(desc(Recipe.scrap_count))
        .limit(10)
    )
    result = await db.execute(stmt)
    recipes = result.scalars().all()
    return [r.__dict__ for r in recipes]


# 3. 레시피 상세 조회
async def get_recipe_detail(
    db: AsyncSession,
    recipe_id: int
) -> Optional[dict]:
    """
    레시피 상세정보 (+재료 리스트 포함)
    """
    stmt = select(Recipe).where(Recipe.recipe_id == recipe_id) # type: ignore
    result = await db.execute(stmt)
    recipe = result.scalar_one_or_none()
    if not recipe:
        return None
    # 재료 리스트 포함
    materials = [
        m.__dict__ for m in recipe.materials
    ] if hasattr(recipe, "materials") else []
    return {
        **recipe.__dict__,
        "materials": materials
    }


# 4. 만개의 레시피 URL 생성
async def get_recipe_url(
    db: AsyncSession,
    recipe_id: int
) -> str:
    """
    만개의 레시피 상세페이지 URL 반환
    """
    return f"https://www.10000recipe.com/recipe/{recipe_id}" # 예시


# 5. 레시피 별점 평균 조회 (임시)
async def get_recipe_rating(
    db: AsyncSession,
    recipe_id: int
) -> float:
    """
    레시피 별점 평균값 조회
    (예시: Rating 테이블에서 평균 계산)
    """
    stmt = (
        select(func.avg(Rating.rating))
        .where(Rating.recipe_id == recipe_id) # type: ignore
    )
    result = await db.execute(stmt)
    avg_rating = result.scalar()
    return float(avg_rating) if avg_rating is not None else 0.0


# 6. 레시피 별점 등록 (임시)
async def set_recipe_rating(
    db: AsyncSession,
    recipe_id: int,
    rating: float
) -> float:
    """
    레시피 별점 등록
    (예시: 단순 추가/저장, 테이블 구조에 맞게 수정)
    """
    new_rating = Rating(recipe_id=recipe_id, rating=rating)
    db.add(new_rating)
    await db.commit()
    return rating


# 7. 후기(코멘트) 목록 조회 (임시)
async def get_comments(
    db: AsyncSession,
    recipe_id: int,
    page: int,
    size: int
) -> Tuple[List[dict], int]:
    """
    후기(코멘트) 목록 + 전체 개수 (페이지네이션)
    """
    offset = (page - 1) * size
    stmt = (
        select(Comment)
        .where(Comment.recipe_id == recipe_id) # type: ignore
        .order_by(desc(Comment.comment_id))
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    comments = result.scalars().all()
    # 전체 개수
    count_stmt = select(func.count()).where(Comment.recipe_id == recipe_id) # type: ignore
    total = (await db.execute(count_stmt)).scalar()
    return [c.__dict__ for c in comments], total


# 8. 후기(코멘트) 등록 (임시)
async def add_comment(
    db: AsyncSession,
    recipe_id: int,
    comment_body
) -> dict:
    """
    후기(코멘트) 등록
    (예시: Comment 테이블, user_id 등 필요시 추가)
    """
    # 실제로는 user_id 등 인증정보에서 받아야 함
    new_comment = Comment(recipe_id=recipe_id, user_id=1, comment=comment_body.comment)
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return new_comment.__dict__
