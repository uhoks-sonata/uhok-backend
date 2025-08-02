"""
레시피 서비스 API 라우터
- 재료소진/레시피추천 탭부터 상세, 별점, 후기, 상품 추천까지
"""

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from services.recipe.schemas.recipe_schema import (
    RecipeListResponse,         # {"recipes": [...]}
    RecipeDetailResponse,       # 상세 {"recipe_id": ..., ...}
    RecipeUrlResponse,          # {"url": ...}
    RecipeRatingResponse,       # {"recipe_id": ..., "rating": ...}
    CommentCreate,              # 후기 작성용
    CommentListResponse,        # {"comments": [...], "total": ...}
    ProductInfo                 # 상품추천용
)
from services.recipe.crud.recipe_crud import (
    get_recipes_by_ingredients,
    search_recipes_by_keyword,
    get_recipe_detail,
    get_recipe_url,
    get_recipe_rating,
    set_recipe_rating,
    get_comments,
    add_comment
)
from services.recipe.database import get_db

router = APIRouter()

# ------------------------------
# 재료소진 추천 탭
# ------------------------------

@router.get("/by-ingredients", response_model=RecipeListResponse)
async def by_ingredients(
    ingredient: List[str] = Query(..., min_length=3, description="최소 3개 재료명 (반복)"),
    amount: Optional[List[str]] = Query(None, description="각 재료별 분량 (반복, 옵션)"),
    count: Optional[int] = Query(None, description="소진 횟수 (옵션)"),
    db: AsyncSession = Depends(get_db)
):
    """
    입력 재료(+분량/횟수) 기반 레시피 추천 (최대 10개)
    """
    recipes = await get_recipes_by_ingredients(db, ingredient, amount, count)
    return {"recipes": recipes}


# ------------------------------
# 레시피명 추천 탭
# ------------------------------

@router.get("/search", response_model=RecipeListResponse)
async def search_recipe(
    recipe: str = Query(..., description="레시피 키워드"),
    db: AsyncSession = Depends(get_db)
):
    """
    레시피명(키워드) 기반 레시피 추천 (최대 10개)
    """
    recipes = await search_recipes_by_keyword(db, recipe)
    return {"recipes": recipes}


# ------------------------------
# 레시피 상세
# ------------------------------

@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe(
    recipe_id: int = Path(..., description="레시피 PK"),
    db: AsyncSession = Depends(get_db)
):
    """
    레시피 상세정보(+재료 리스트)
    """
    detail = await get_recipe_detail(db, recipe_id)
    return detail


# ------------------------------
# 만개의 레시피 URL
# ------------------------------

@router.get("/{recipe_id}/url", response_model=RecipeUrlResponse)
async def get_recipe_url_api(
    recipe_id: int = Path(...),
    db: AsyncSession = Depends(get_db)
):
    """
    만개의 레시피 상세페이지 URL 반환
    """
    url = await get_recipe_url(db, recipe_id)
    return {"url": url}


# ------------------------------
# 레시피 별점 조회/작성
# ------------------------------

@router.get("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def get_rating(
    recipe_id: int = Path(...),
    db: AsyncSession = Depends(get_db)
):
    """
    레시피 별점 평균 조회
    """
    rating = await get_recipe_rating(db, recipe_id)
    return {"recipe_id": recipe_id, "rating": rating}

@router.post("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def post_rating(
    recipe_id: int = Path(...),
    body: RecipeRatingResponse = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """
    레시피 별점 작성(등록)
    """
    rating = await set_recipe_rating(db, recipe_id, body.rating)
    return {"recipe_id": recipe_id, "rating": rating}


# ------------------------------
# 후기(코멘트) 작성/목록
# ------------------------------

@router.post("/{recipe_id}/comment")
async def create_comment(
    recipe_id: int = Path(...),
    body: CommentCreate = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    레시피 후기(코멘트) 등록
    """
    comment = await add_comment(db, recipe_id, body)
    return comment

@router.get("/{recipe_id}/comments", response_model=CommentListResponse)
async def list_comments(
    recipe_id: int = Path(...),
    page: int = Query(1),
    size: int = Query(10),
    db: AsyncSession = Depends(get_db)
):
    """
    레시피 후기(코멘트) 목록
    """
    comments, total = await get_comments(db, recipe_id, page, size)
    return {"comments": comments, "total": total}


# ------------------------------
# 콕/홈쇼핑 관련 상품 추천
# ------------------------------

@router.get("/kok", response_model=List[ProductInfo])
async def recommend_kok_product(
    ingredient: str = Query(..., description="재료명"),
    db: AsyncSession = Depends(get_db)
):
    """
    콕 쇼핑몰 내 관련 상품 추천
    """
    # from common.recommend.kok_product import recommend_kok_products_by_ingredient
    # 실제 추천로직 함수 import하여 사용
    return await recommend_kok_products_by_ingredient(db, ingredient)

@router.get("/home-shopping", response_model=List[ProductInfo])
async def recommend_home_product(
    ingredient: str = Query(..., description="재료명"),
    db: AsyncSession = Depends(get_db)
):
    """
    홈쇼핑 내 관련 상품 추천
    """
    # from common.recommend.home_product import recommend_home_products_by_ingredient
    return await recommend_home_products_by_ingredient(db, ingredient)
