"""
레시피/재료/후기/별점 DB 접근(CRUD) 함수 (MariaDB)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple

from services.recipe.models.recipe_model import Recipe, Material, RecipeComment, RecipeRating

async def get_recipe_detail(
        db: AsyncSession,
        recipe_id: int
) -> Optional[dict]:
    """
        주어진 recipe_id에 해당하는 레시피 상세정보와 재료 리스트를 반환
        """
    stmt = (
        select(Recipe).where(Recipe.recipe_id == recipe_id) # type: ignore
    )
    result = await db.execute(stmt)
    recipe = result.scalar_one_or_none()
    if not recipe:
        return None
    stmt2 = (
        select(Material).where(Material.recipe_id == recipe_id) # type: ignore
    )
    mats = (await db.execute(stmt2)).scalars().all()
    materials = [m.__dict__ for m in mats]
    return {**recipe.__dict__, "materials": materials}

async def get_recipe_url(
        db: AsyncSession,
        recipe_id: int
) -> Optional[str]:
    """
        레시피의 만개의 레시피 URL을 반환 (DB에서 컬럼 조회)
    """
    stmt = (
        select(Recipe.recipe_url).where(Recipe.recipe_id == recipe_id) # type: ignore
    )
    result = await db.execute(stmt)
    url = result.scalar_one_or_none()
    return url

async def get_recipe_comments(
        db: AsyncSession,
        recipe_id: int,
        page: int,
        size: int
) -> Tuple[List[dict], int]:
    """
        주어진 레시피의 후기 목록(페이지네이션)과 총 개수를 반환
    """
    offset = (page - 1) * size
    stmt = (
        select(RecipeComment)
        .where(RecipeComment.recipe_id == recipe_id) # type: ignore
        .offset(offset)
        .limit(size)
    )
    comments = (await db.execute(stmt)).scalars().all()
    count_stmt = (
        select(func.count()).where(RecipeComment.recipe_id == recipe_id) # type: ignore
    )
    total = (await db.execute(count_stmt)).scalar()
    return [c.__dict__ for c in comments], total

async def add_recipe_comment(
        db: AsyncSession,
        recipe_id: int,
        user_id: int,
        comment: str
) -> dict:
    """
        새로운 후기(코멘트)를 등록하고 저장된 내용을 반환
    """
    new_comment = RecipeComment(recipe_id=recipe_id, user_id=user_id, comment=comment)
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return new_comment.__dict__

async def get_recipe_rating(
        db: AsyncSession,
        recipe_id: int
) -> float:
    """
        해당 레시피의 별점 평균값을 반환
    """
    stmt = (
        select(func.avg(RecipeRating.rating))
        .where(RecipeRating.recipe_id == recipe_id) # type: ignore
    )
    avg_rating = (await db.execute(stmt)).scalar()
    return float(avg_rating) if avg_rating is not None else 0.0

async def set_recipe_rating(
        db: AsyncSession,
        recipe_id: int,
        user_id: int,
        rating: float
) -> float:
    """새로운 별점을 등록하고 저장된 값을 반환"""
    new_rating = RecipeRating(recipe_id=recipe_id, user_id=user_id, rating=rating)
    db.add(new_rating)
    await db.commit()
    return rating

