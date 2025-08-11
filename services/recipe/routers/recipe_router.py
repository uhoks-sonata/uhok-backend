"""
레시피 상세/재료/만개의레시피 url, 후기, 별점 API 라우터 (MariaDB)
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
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
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

# 로거 초기화
logger = get_logger("recipe_router")

router = APIRouter(prefix="/api/recipes", tags=["Recipe"])

@router.get("/by-ingredients")
async def by_ingredients(
    ingredient: List[str] = Query(..., min_length=3, description="식재료 리스트 (최소 3개)"),
    amount: Optional[List[str]] = Query(None, description="각 재료별 분량(옵션)"),
    unit: Optional[List[str]] = Query(None, description="각 재료별 단위(옵션)"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
    current_user = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    재료/분량/단위 기반 레시피 추천 (페이지네이션)
    - matched_ingredient_count 포함
    - 응답: recipes(추천 목록), page(현재 페이지), total(전체 결과 개수)
    """
    logger.info(f"재료 기반 레시피 추천 API 호출: user_id={current_user.user_id}, 재료={ingredient}, 페이지={page}, 크기={size}")
    
    # amount/unit 길이 체크
    if (amount and len(amount) != len(ingredient)) or (unit and len(unit) != len(ingredient)):
        logger.warning(f"파라미터 길이 불일치: ingredient={len(ingredient)}, amount={len(amount) if amount else 0}, unit={len(unit) if unit else 0}")
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="amount, unit 파라미터 개수가 ingredient와 일치해야 합니다.")
    
    # 추천 결과 + 전체 개수 반환
    recipes, total = await recommend_recipes_by_ingredients(
        db, ingredient, amount, unit, page=page, size=size
    )
    
    logger.info(f"재료 기반 레시피 추천 완료: 총 {total}개, 현재 페이지 {len(recipes)}개")
    
    # 재료 기반 레시피 검색 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_search_by_ingredients", 
            event_data={
                "ingredients": ingredient,
                "amount": amount,
                "unit": unit,
                "page": page,
                "size": size,
                "total_results": total
            }
        )
    
    return {
        "recipes": recipes,
        "page": page,
        "total": total
    }


# 하이브리드 검색 엔드포인트 제거됨


@router.get("/search")
async def search_recipe(
    recipe: str = Query(..., description="레시피명 또는 식재료 키워드"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
    method: str = Query("recipe", pattern="^(recipe|ingredient)$", description="검색 방식: recipe|ingredient"),
    current_user = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피명(키워드) 기반 유사 레시피 추천 (페이지네이션)
    - 모델에서 유사 recipe_id 추천받아 상세조회 및 결과 반환
    - 응답: recipes(추천 목록), page(현재 페이지), total(전체 결과 개수)
    """
    logger.info(f"레시피 키워드 검색 API 호출: user_id={current_user.user_id}, keyword={recipe}, method={method}, 페이지={page}, 크기={size}")
    
    recipes, total = await search_recipes_by_keyword(db, recipe, page=page, size=size, method=method)
    
    logger.info(f"레시피 키워드 검색 완료: 총 {total}개, 현재 페이지 {len(recipes)}개")
    
    # 레시피 키워드 검색 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_search_by_keyword", 
            event_data={
                "keyword": recipe,
                "page": page,
                "size": size,
                "method": method,
                "total_results": total
            }
        )
    
    return {
        "recipes": recipes,
        "page": page,
        "total": total
    }

@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe(
        recipe_id: int,
        current_user = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 상세 정보 + 재료 리스트 + 만개의레시피 url 조회
    """
    logger.info(f"레시피 상세 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    result = await get_recipe_detail(db, recipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="레시피가 존재하지 않습니다.")
    
    # 레시피 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_detail_view", 
            event_data={
                "recipe_id": recipe_id,
                "recipe_name": result.get("cooking_name") or result.get("recipe_title")
            }
        )
    
    return result


@router.get("/{recipe_id}/url", response_model=RecipeUrlResponse)
async def get_recipe_url_api(
    recipe_id: int,
    current_user = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    만개의 레시피 URL 동적 생성하여 반환
    """
    logger.info(f"만개의 레시피 URL 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    url = get_recipe_url(recipe_id)
    
    # 레시피 URL 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_url_view", 
            event_data={"recipe_id": recipe_id}
        )
    
    return {"url": url}


@router.get("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def get_rating(
        recipe_id: int,
        current_user = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 별점 평균 조회
    """
    logger.info(f"레시피 별점 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    rating = await get_recipe_rating(db, recipe_id)
    
    # 레시피 별점 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_rating_view", 
            event_data={"recipe_id": recipe_id, "rating": rating}
        )
    
    return {"recipe_id": recipe_id, "rating": rating}


@router.post("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def post_rating(
        recipe_id: int,
        req: RecipeRatingCreate,
        current_user = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 별점 등록 (0~5 정수만 허용)
    """
    logger.info(f"레시피 별점 등록 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}, rating={req.rating}")
    # 실제 서비스에서는 user_id를 인증에서 추출
    rating = await set_recipe_rating(db, recipe_id, user_id=current_user.user_id, rating=int(req.rating))
    
    # 레시피 별점 등록 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_rating_create", 
            event_data={
                "recipe_id": recipe_id,
                "rating": int(req.rating)
            }
        )
    
    return {"recipe_id": recipe_id, "rating": rating}


@router.get("/recipes/kok")
async def get_kok_products(
    ingredient: str = Query(..., description="검색할 식재료명(예: 감자, 양파 등)"),
    current_user = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    콕 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
    - 반환 필드명은 kok 모델 변수명(소문자)과 100% 일치
    """
    logger.info(f"콕 상품 검색 API 호출: user_id={current_user.user_id}, ingredient={ingredient}")
    products = await get_kok_products_by_ingredient(db, ingredient)
    
    # 식재료 기반 상품 검색 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="ingredient_product_search", 
            event_data={
                "ingredient": ingredient,
                "product_count": len(products)
            }
        )
    
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
#
# # 소진 횟수 포함
# @router.get("/by-ingredients")
# async def by_ingredients(
#     ingredient: List[str] = Query(..., min_length=3, description="식재료 리스트 (최소 3개)"),
#     amount: Optional[List[str]] = Query(None, description="각 재료별 분량(옵션)"),
#     unit: Optional[List[str]] = Query(None, description="각 재료별 단위(옵션)"),
#     consume_count: Optional[int] = Query(None, description="재료 소진 횟수(옵션)"),
#     page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
#     size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     재료/분량/단위/소진횟수 기반 레시피 추천 (페이지네이션)
#     - matched_ingredient_count 포함
#     - 응답: recipes(추천 목록), page(현재 페이지), total(전체 결과 개수)
#     """
#     # amount/unit 길이 체크
#     if (amount and len(amount) != len(ingredient)) or (unit and len(unit) != len(ingredient)):
#         from fastapi import HTTPException
#         raise HTTPException(status_code=400, detail="amount, unit 파라미터 개수가 ingredient와 일치해야 합니다.")
#     # 추천 결과 + 전체 개수 반환
#     recipes, total = await recommend_recipes_by_ingredients(
#         db, ingredient, amount, unit, consume_count, page=page, size=size
#     )
#     return {
#         "recipes": recipes,
#         "page": page,
#         "total": total
#     }