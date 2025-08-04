"""
레시피 상세/재료/만개의레시피 url, 후기, 별점 API 라우터 (MariaDB)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.recipe.schemas.recipe_schema import (
    RecipeDetailResponse,
    RecipeUrlResponse,
    RecipeRatingCreate,
    RecipeRatingResponse,
    # RecipeCommentCreate,
    # RecipeComment,
    # RecipeCommentListResponse
)
from services.recipe.crud.recipe_crud import (
    get_recipe_detail,
    get_recipe_url,
    get_recipe_rating,
    set_recipe_rating,
    # get_recipe_comments,
    # add_recipe_comment,
)
from common.database.mariadb_service import get_maria_service_db

router = APIRouter()


@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe(
        recipe_id: int,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
        레시피 상세 정보 + 재료 리스트 조회
    """
    result = await get_recipe_detail(db, recipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="레시피가 존재하지 않습니다.")
    return result


@router.get("/{recipe_id}/url", response_model=RecipeUrlResponse)
async def get_recipe_url_api(
        recipe_id: int,
):
    """
        만개의 레시피 URL 동적 생성하여 반환
    """
    url = await get_recipe_url(recipe_id)
    if not url:
        raise HTTPException(status_code=404, detail="레시피 URL이 존재하지 않습니다.")
    return {"url": url}


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
    rating = await set_recipe_rating(db, recipe_id, user_id=1, rating=int(req.rating))
    return {"recipe_id": recipe_id, "rating": rating}


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
