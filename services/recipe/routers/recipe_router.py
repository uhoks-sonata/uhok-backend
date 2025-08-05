"""
레시피 상세/재료/만개의레시피 url, 후기, 별점 API 라우터 (MariaDB)
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from services.recipe.schemas.recipe_schema import (
    RecipeDetailResponse,
    RecipeUrlResponse,
    RecipeRatingCreate,
    RecipeRatingResponse
)
from services.recipe.crud.recipe_crud import (
    get_recipe_detail,
    get_recipe_url,
    recommend_recipes_by_ingredients,
    search_recipes_by_keyword,
    get_recipe_rating,
    set_recipe_rating
)
from services.kok.crud.kok_crud import get_kok_products_by_ingredient

from common.database.mariadb_service import get_maria_service_db

router = APIRouter(prefix="/api/recipes", tags=["Recipe"])

@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe(
        recipe_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 상세 정보 + 재료 리스트 + 만개의레시피 url 조회
    """
    result = await get_recipe_detail(db, recipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="레시피가 존재하지 않습니다.")
    return result


@router.get("/{recipe_id}/url", response_model=RecipeUrlResponse)
async def get_recipe_url_api(recipe_id: int):
    """
    만개의 레시피 URL 동적 생성하여 반환
    """
    url = get_recipe_url(recipe_id)
    return {"url": url}


@router.get("/by-ingredients")
async def by_ingredients(
    ingredient: List[str] = Query(..., min_length=3, description="식재료 리스트 (최소 3개)"),
    amount: Optional[List[str]] = Query(None, description="각 재료별 분량(옵션)"),
    unit: Optional[List[str]] = Query(None, description="각 재료별 단위(옵션)"),
    consume_count: Optional[int] = Query(None, description="재료 소진 횟수(옵션)"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    재료/분량/단위/소진횟수 기반 레시피 추천 (페이지네이션)
    - matched_ingredient_count 포함
    - 응답: recipes(추천 목록), page(현재 페이지), total(전체 결과 개수)
    """
    # amount/unit 길이 체크
    if (amount and len(amount) != len(ingredient)) or (unit and len(unit) != len(ingredient)):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="amount, unit 파라미터 개수가 ingredient와 일치해야 합니다.")
    # 추천 결과 + 전체 개수 반환
    recipes, total = await recommend_recipes_by_ingredients(
        db, ingredient, amount, unit, consume_count, page=page, size=size
    )
    return {
        "recipes": recipes,
        "page": page,
        "total": total
    }


@router.get("/search")
async def search_recipe(
    recipe: str = Query(..., description="레시피명(키워드)"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피명(키워드) 기반 유사 레시피 추천 (페이지네이션)
    - 모델에서 유사 recipe_id 추천받아 상세조회 및 결과 반환
    - 응답: recipes(추천 목록), page(현재 페이지), total(전체 결과 개수)
    """
    recipes, total = await search_recipes_by_keyword(db, recipe, page=page, size=size)
    return {
        "recipes": recipes,
        "page": page,
        "total": total
    }


@router.get("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def get_rating(
        recipe_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 별점 평균 조회
    """
    rating = await get_recipe_rating(db, recipe_id)
    return {"recipe_id": recipe_id, "rating": rating}


@router.post("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def post_rating(
        recipe_id: int,
        req: RecipeRatingCreate,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 별점 등록 (0~5 정수만 허용)
    """
    # 실제 서비스에서는 user_id를 인증에서 추출
    rating = await set_recipe_rating(db, recipe_id, user_id=1, rating=int(req.rating))
    return {"recipe_id": recipe_id, "rating": rating}


@router.get("/recipes/kok")
async def get_kok_products(
    ingredient: str = Query(..., description="검색할 식재료명(예: 감자, 양파 등)"),
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    콕 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
    - 반환 필드명은 kok 모델 변수명(소문자)과 100% 일치
    """
    products = await get_kok_products_by_ingredient(db, ingredient)
    return products


###########################################################
# @router.get("/{recipe_id}/comments", response_model=RecipeCommentListResponse)
# async def list_comments(
#         recipe_id: int,
#         page: int = 1,
#         size: int = 10,
#         db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#         레시피별 후기(코멘트) 목록(페이지네이션)
#     """
#     comments, total = await get_recipe_comments(db, recipe_id, page, size)
#     return {"comments": comments, "total": total}
#
#
# @router.post("/{recipe_id}/comment", response_model=RecipeComment)
# async def create_comment(
#         recipe_id: int,
#         req: RecipeCommentCreate,
#         db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#         레시피 후기(코멘트) 등록
#     """
#     # 실서비스에서는 user_id를 인증에서 추출
#     comment = await add_recipe_comment(db, recipe_id, user_id=1, comment=req.comment)
#     return comment
