"""
레시피 상세/재료/만개의레시피 url, 후기, 별점 API 라우터 (MariaDB)
- HTTP 요청/응답을 담당
- 파라미터 파싱, 유저 인증/권한 확인, 의존성 주입 (Depends)
- 비즈니스 로직은 호출만 하고 직접 DB 처리(트랜잭션)는 하지 않음
- 트랜잭션 관리(commit/rollback)를 담당
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, Path, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import pandas as pd
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from common.dependencies import get_current_user
from common.database.mariadb_service import get_maria_service_db
# from common.database.postgres_recommend import get_postgres_recommend_db # Removed
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from ..utils.remote_ml_adapter import _call_ml_search_service

from services.user.schemas.user_schema import UserOut
from services.recipe.schemas.recipe_schema import (
    RecipeDetailResponse,
    RecipeUrlResponse,
    RecipeRatingCreate,
    RecipeRatingResponse,
    RecipeByIngredientsListResponse,
    RecipeIngredientStatusResponse,
    ProductRecommendResponse
)
from services.recipe.crud.recipe_crud import (
    get_recipe_detail,
    get_recipe_url,
    recommend_recipes_combination_1,
    recommend_recipes_combination_2,
    recommend_recipes_combination_3,
    # recommend_by_recipe_pgvector, # Removed
    get_recipe_rating,
    set_recipe_rating,
    get_recipe_ingredients_status
)

# from ..utils.recommend_service import get_db_vector_searcher # Removed
# from ..utils.ports import VectorSearcherPort # Still needed for type hinting the port
from services.recipe.utils.combination_tracker import CombinationTracker
from services.recipe.utils.product_recommend import recommend_for_ingredient
from services.recipe.utils.simple_cache import recipe_cache

# combination_tracker 인스턴스 생성
combination_tracker = CombinationTracker()

# 로거 초기화
logger = get_logger("recipe_router")
router = APIRouter(prefix="/api/recipes", tags=["Recipe"])

# ============================================================================
# 1. 재료 기반 레시피 추천 API
# ============================================================================
@router.get("/by-ingredients", response_model=RecipeByIngredientsListResponse)
async def by_ingredients(
    request: Request,
    ingredient: List[str] = Query(..., min_length=3, description="식재료 리스트 (최소 3개)"),
    amount: Optional[List[float]] = Query(None, description="각 재료별 분량 (amount 또는 unit 중 하나는 필수)"),
    unit: Optional[List[str]] = Query(None, description="각 재료별 단위 (amount 또는 unit 중 하나는 필수)"),
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(5, ge=1, le=50, description="페이지당 결과 개수"),
    current_user = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    페이지별로 다른 조합을 생성하여 반환
    - 1페이지: 1조합 (전체 레시피 풀)
    - 2페이지: 2조합 (1조합 제외한 레시피 풀)
    - 3페이지: 3조합 (1조합, 2조합 제외한 레시피 풀)
    """
    logger.debug(f"재료 기반 레시피 추천 시작: user_id={current_user.user_id}, 재료={ingredient}, 페이지={page}")
    logger.info(f"재료 기반 레시피 추천 API 호출: user_id={current_user.user_id}, 재료={ingredient}, 분량={amount}, 단위={unit}, 페이지={page}, 크기={size}")
    
    # amount 또는 unit 중 하나는 필수
    if amount is None and unit is None:
        logger.warning(f"amount와 unit 모두 제공되지 않음: user_id={current_user.user_id}")
        raise HTTPException(status_code=400, detail="amount 또는 unit 중 하나는 반드시 제공해야 합니다.")
    
    # amount가 제공된 경우 길이 체크
    if amount is not None and len(amount) != len(ingredient):
        logger.warning(f"amount 길이 불일치: user_id={current_user.user_id}, ingredient={len(ingredient)}, amount={len(amount)}")
        raise HTTPException(status_code=400, detail="amount 파라미터 개수가 ingredient와 일치해야 합니다.")
    
    # unit이 제공된 경우 길이 체크
    if unit is not None and len(unit) != len(ingredient):
        logger.warning(f"unit 길이 불일치: user_id={current_user.user_id}, ingredient={len(ingredient)}, unit={len(unit)}")
        raise HTTPException(status_code=400, detail="unit 파라미터 개수가 ingredient와 일치해야 합니다.")
    
    # 페이지별 조합 번호 결정
    combination_number = page
    
    # 재료 정보 해시 생성 (amount 또는 unit이 None인 경우 기본값 사용)
    amounts_for_hash = amount if amount is not None else [1.0] * len(ingredient)
    units_for_hash = unit if unit is not None else [""] * len(ingredient)
    ingredients_hash = combination_tracker.generate_ingredients_hash(ingredient, amounts_for_hash, units_for_hash)
    
    # 현재 조합에서 사용된 레시피 ID들 조회 (같은 조합 내에서만 제외)
    excluded_recipe_ids = combination_tracker.get_excluded_recipe_ids(
        current_user.user_id, ingredients_hash, combination_number
    )
    
    # 조합별 레시피 추천 (성능 측정 포함)
    try:
        import time
        start_time = time.time()
        
        if combination_number == 1:
            recipes, total = await recommend_recipes_combination_1(
                db, ingredient, amount, unit, 1, size, current_user.user_id
            )
            logger.debug(f"조합 1 레시피 추천 성공: user_id={current_user.user_id}, 결과 수={len(recipes)}")
        elif combination_number == 2:
            recipes, total = await recommend_recipes_combination_2(
                db, ingredient, amount, unit, 1, size, excluded_recipe_ids, current_user.user_id
            )
            logger.debug(f"조합 2 레시피 추천 성공: user_id={current_user.user_id}, 결과 수={len(recipes)}")
        elif combination_number == 3:
            recipes, total = await recommend_recipes_combination_3(
                db, ingredient, amount, unit, 1, size, excluded_recipe_ids, current_user.user_id
            )
            logger.debug(f"조합 3 레시피 추천 성공: user_id={current_user.user_id}, 결과 수={len(recipes)}")
        else:
            # 3페이지 이상은 빈 결과 반환
            logger.debug(f"3페이지 이상 요청: user_id={current_user.user_id}, page={page}")
            return {
                "recipes": [],
                "page": page,
                "total": 0,
                "combination_number": combination_number,
                "has_more_combinations": False
            }
        
        # 성능 측정 완료
        execution_time = time.time() - start_time
        logger.info(f"조합 {combination_number} 추천 완료: user_id={current_user.user_id}, 실행시간={execution_time:.3f}초, 결과수={len(recipes)}")
        
    except Exception as e:
        logger.error(f"레시피 추천 실패: user_id={current_user.user_id}, combination_number={combination_number}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 추천 중 오류가 발생했습니다.")
    
    # 사용된 레시피 ID들을 추적 시스템에 저장 (현재 조합만)
    if recipes:
        used_recipe_ids = [recipe["recipe_id"] for recipe in recipes]
        combination_tracker.track_used_recipes(
            current_user.user_id, ingredients_hash, combination_number, used_recipe_ids
        )
    
    logger.info(f"조합 {combination_number} 레시피 추천 완료: user_id={current_user.user_id}, 총 {total}개, 현재 페이지 {len(recipes)}개")
    
    # 재료 기반 레시피 검색 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
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
                "total_results": total,
                "combination_number": combination_number
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {
        "recipes": recipes,
        "page": page,
        "total": total,
        "combination_number": combination_number,
        "has_more_combinations": combination_number < 3
    }


@router.get("/cache/stats")
async def get_cache_stats(current_user = Depends(get_current_user)):
    """
    레시피 캐시 통계 조회
    - 캐시 크기 및 상태 정보
    """
    logger.debug(f"캐시 통계 조회 시작: user_id={current_user.user_id}")
    logger.info(f"캐시 통계 조회 요청: user_id={current_user.user_id}")
    
    try:
        stats = recipe_cache.get_stats()
        logger.debug(f"캐시 통계 조회 성공: user_id={current_user.user_id}")
    except Exception as e:
        logger.error(f"캐시 통계 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="캐시 통계 조회 중 오류가 발생했습니다.")
    
    return {
        "cache_stats": stats,
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# 2. 레시피 검색 API
# ============================================================================
@router.get("/search")
async def search_recipe(
    request: Request,
    recipe: str = Query(..., description="레시피명 또는 식재료 키워드"),
    page: int = Query(1, ge=1),
    size: int = Query(15, ge=1, le=50),
    method: str = Query("recipe", pattern="^(recipe|ingredient)$", description="검색 방식: recipe|ingredient"),
    current_user = Depends(get_current_user),
    mariadb: AsyncSession = Depends(get_maria_service_db),
    background_tasks: BackgroundTasks = None,
):
    """
    검색/추천 엔드포인트 (페이지네이션 정확 반영).
    - method='recipe'일 때만 벡터 유사도 검색을 위해 ML 서비스를 호출합니다.
    - method='ingredient'는 DB 검색만 수행합니다.
    """
    logger.info(f"레시피 검색 호출: uid={current_user.user_id}, kw={recipe}, method={method}, p={page}, s={size}")
    start_time = time.time()

    if method == "recipe":
        try:
            # ML 서비스 호출
            search_results = await _call_ml_search_service(
                query=recipe,
                top_k=page * size + 1 # 다음 페이지 확인을 위해 1개 더 요청
            )
            
            if not search_results:
                return {"recipes": [], "page": page, "total": 0}

            # ID 리스트 추출
            result_ids = [item['recipe_id'] for item in search_results]
            
            # MariaDB에서 상세 정보 조회
            from services.recipe.models.recipe_model import Recipe
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
                .where(Recipe.recipe_id.in_(result_ids))
            )
            detail_rows = (await mariadb.execute(detail_stmt)).all()
            df = pd.DataFrame(detail_rows, columns=[
                "RECIPE_ID","RECIPE_TITLE","COOKING_NAME","SCRAP_COUNT","COOKING_CASE_NAME","COOKING_CATEGORY_NAME",
                "COOKING_INTRODUCTION","NUMBER_OF_SERVING","THUMBNAIL_URL"
            ])

            # ML 서비스 결과의 순서대로 정렬
            order_map = {rid: i for i, rid in enumerate(result_ids)}
            df["__order__"] = df["RECIPE_ID"].map(order_map)
            df = df.sort_values("__order__").drop(columns="__order__").reset_index(drop=True)

        except Exception as e:
            logger.error(f"ML 서비스 기반 레시피 검색 실패: user_id={current_user.user_id}, keyword={recipe}, error={str(e)}")
            raise HTTPException(status_code=500, detail="레시피 검색 중 오류가 발생했습니다.")

    else: # method == "ingredient"
        # 기존 재료 검색 로직 유지
        from services.recipe.models.recipe_model import Material
        ingredients = [i.strip() for i in (recipe or "").split(",") if i.strip()]
        if not ingredients:
            return {"recipes": [], "page": page, "total": 0}

        total_stmt = select(func.count(func.distinct(Material.recipe_id)))\
            .where(Material.material_name.in_(ingredients))\
            .having(func.count(func.distinct(Material.material_name)) == len(ingredients))
        total_count = (await mariadb.execute(total_stmt)).scalar_one_or_none() or 0

        start_offset = (page - 1) * size
        ids_stmt = select(Material.recipe_id)\
            .where(Material.material_name.in_(ingredients))\
            .group_by(Material.recipe_id)\
            .having(func.count(func.distinct(Material.material_name)) == len(ingredients))\
            .order_by(desc(func.count(func.distinct(Material.material_name))))\
            .offset(start_offset).limit(size)
        page_ids = (await mariadb.execute(ids_stmt)).scalars().all()

        if not page_ids:
            return {"recipes": [], "page": page, "total": total_count}
        
        detail_stmt = select(Recipe).where(Recipe.recipe_id.in_(page_ids))
        detail_rows = (await mariadb.execute(detail_stmt)).scalars().all()
        df = pd.DataFrame([r.__dict__ for r in detail_rows])

    # 페이지네이션 및 결과 포맷팅
    start_index, end_index = (page - 1) * size, page * size
    has_more = len(df) > size
    page_df = df.iloc[:size] if not df.empty else df
    total_approx = start_index + len(page_df) + (1 if has_more else 0)

    execution_time = time.time() - start_time
    logger.info(f"레시피 검색 완료: uid={current_user.user_id}, kw={recipe}, method={method}, 실행시간={execution_time:.3f}초, 결과수={len(page_df)}")

    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="recipe_search_by_keyword",
            event_data={
                "keyword": recipe,
                "page": page,
                "size": size,
                "method": method,
                "row_count": int(len(page_df)),
                "has_more": has_more,
                "execution_time_seconds": round(execution_time, 3),
            },
            **http_info
        )

    return {
        "recipes": page_df.to_dict(orient="records"),
        "page": page,
        "total": total_approx,
    }

# ============================================================================
# 3. 레시피 상세 정보 API
# ============================================================================
@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
async def get_recipe(
        request: Request,
        current_user = Depends(get_current_user),
        recipe_id: int = Path(..., description="레시피 ID"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 상세 정보 + 재료 리스트 + 만개의레시피 url 조회
    """
    logger.debug(f"레시피 상세 조회 시작: user_id={current_user.user_id}, recipe_id={recipe_id}")
    logger.info(f"레시피 상세 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    
    try:
        result = await get_recipe_detail(db, recipe_id)
        if not result:
            logger.warning(f"레시피를 찾을 수 없음: recipe_id={recipe_id}, user_id={current_user.user_id}")
            raise HTTPException(status_code=404, detail="레시피가 존재하지 않습니다.")
        logger.debug(f"레시피 상세 조회 성공: recipe_id={recipe_id}, user_id={current_user.user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"레시피 상세 조회 실패: recipe_id={recipe_id}, user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 조회 중 오류가 발생했습니다.")
    
    # 레시피 상세 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_detail_view", 
            event_data={
                "recipe_id": recipe_id,
                "recipe_name": result.get("cooking_name") or result.get("recipe_title")
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return result

# ============================================================================
# 4. 레시피 URL API
# ============================================================================
@router.get("/{recipe_id}/url", response_model=RecipeUrlResponse)
async def get_recipe_url_api(
    request: Request,
    current_user = Depends(get_current_user),
    recipe_id: int = Path(..., description="레시피 ID"),
    background_tasks: BackgroundTasks = None
):
    """
    만개의 레시피 URL 동적 생성하여 반환
    """
    logger.debug(f"레시피 URL 조회 시작: user_id={current_user.user_id}, recipe_id={recipe_id}")
    logger.info(f"만개의 레시피 URL 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    
    try:
        url = get_recipe_url(recipe_id)
        logger.debug(f"레시피 URL 조회 성공: recipe_id={recipe_id}, user_id={current_user.user_id}")
    except Exception as e:
        logger.error(f"레시피 URL 조회 실패: recipe_id={recipe_id}, user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 URL 조회 중 오류가 발생했습니다.")
    
    # 레시피 URL 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_url_view", 
            event_data={"recipe_id": recipe_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"url": url}

# ============================================================================
# 5. 레시피 별점 조회 API
# ============================================================================
@router.get("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def get_rating(
        request: Request,
        current_user: UserOut = Depends(get_current_user),
        recipe_id: int = Path(..., description="레시피 ID"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 별점 평균 조회
    """
    logger.debug(f"레시피 별점 조회 시작: user_id={current_user.user_id}, recipe_id={recipe_id}")
    logger.info(f"레시피 별점 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    
    try:
        rating = await get_recipe_rating(db, recipe_id)
        logger.debug(f"레시피 별점 조회 성공: recipe_id={recipe_id}, rating={rating}, user_id={current_user.user_id}")
    except Exception as e:
        logger.error(f"레시피 별점 조회 실패: recipe_id={recipe_id}, user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 별점 조회 중 오류가 발생했습니다.")
    
    # 레시피 별점 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_rating_view", 
            event_data={"recipe_id": recipe_id, "rating": rating},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"recipe_id": recipe_id, "rating": rating}

# ============================================================================
# 6. 레시피 별점 등록 API
# ============================================================================
@router.post("/{recipe_id}/rating", response_model=RecipeRatingResponse)
async def post_rating(
        request: Request,
        current_user: UserOut = Depends(get_current_user),
        recipe_id: int = Path(..., description="레시피 ID"),
        req: RecipeRatingCreate = Body(...),
        db: AsyncSession = Depends(get_maria_service_db),
        background_tasks: BackgroundTasks = None
):
    """
    레시피 별점 등록 (0~5 정수만 허용)
    """
    logger.debug(f"레시피 별점 등록 시작: user_id={current_user.user_id}, recipe_id={recipe_id}, rating={req.rating}")
    logger.info(f"레시피 별점 등록 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}, rating={req.rating}")
    
    try:
        # 실제 서비스에서는 user_id를 인증에서 추출
        rating = await set_recipe_rating(db, recipe_id, user_id=current_user.user_id, rating=int(req.rating))
        logger.debug(f"레시피 별점 등록 성공: recipe_id={recipe_id}, rating={rating}, user_id={current_user.user_id}")
        
        # 트랜잭션 커밋
        await db.commit()
        
        # 레시피 별점 등록 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="recipe_rating_create", 
                event_data={
                    "recipe_id": recipe_id,
                    "rating": int(req.rating)
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"레시피 별점 등록 완료: recipe_id={recipe_id}, rating={rating}, user_id={current_user.user_id}")
        return {"recipe_id": recipe_id, "rating": rating}
        
    except Exception as e:
        # 트랜잭션 롤백
        await db.rollback()
        logger.error(f"레시피 별점 등록 실패: recipe_id={recipe_id}, user_id={current_user.user_id}, error={e}")
        raise HTTPException(status_code=500, detail="레시피 별점 등록 중 오류가 발생했습니다.")

# ============================================================================
# 7. 레시피 식재료 상태 API
# ============================================================================
@router.get("/{recipe_id}/status", response_model=RecipeIngredientStatusResponse)
async def get_recipe_ingredients_status_handler(
    request: Request,
    recipe_id: int = Path(..., description="레시피 ID"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    레시피 상세페이지에서 사용자의 식재료 보유/장바구니/미보유 상태 조회
    
    Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
    비즈니스 로직은 CRUD 계층에 위임
    """
    logger.debug(f"레시피 식재료 상태 조회 시작: user_id={current_user.user_id}, recipe_id={recipe_id}")
    logger.info(f"레시피 식재료 상태 조회 API 호출: user_id={current_user.user_id}, recipe_id={recipe_id}")
    
    try:
        # CRUD 계층에 식재료 상태 조회 위임
        result = await get_recipe_ingredients_status(db, current_user.user_id, recipe_id)
        
        if not result:
            logger.warning(f"레시피 식재료 상태를 찾을 수 없음: recipe_id={recipe_id}, user_id={current_user.user_id}")
            raise HTTPException(status_code=404, detail="레시피를 찾을 수 없거나 식재료 정보가 없습니다.")
        logger.debug(f"레시피 식재료 상태 조회 성공: recipe_id={recipe_id}, user_id={current_user.user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"레시피 식재료 상태 조회 실패: recipe_id={recipe_id}, user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="레시피 식재료 상태 조회 중 오류가 발생했습니다.")
    
    # 레시피 식재료 상태 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="recipe_ingredients_status_view", 
            event_data={
                "recipe_id": recipe_id,
                "total_ingredients": result["summary"]["total_ingredients"],
                "owned_count": result["summary"]["owned_count"],
                "cart_count": result["summary"]["cart_count"],
                "not_owned_count": result["summary"]["not_owned_count"]
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return RecipeIngredientStatusResponse(**result)

# ============================================================================
# 8. 식재료 상품 추천 API
# ============================================================================
@router.get("/{ingredient}/product-recommend", response_model=ProductRecommendResponse)
async def get_ingredient_product_recommendations(
    request: Request,
    ingredient: str = Path(..., description="추천받을 식재료명"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    특정 식재료에 대한 콕 상품과 홈쇼핑 상품 추천
    
    Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
    비즈니스 로직은 product_recommend 모듈에 위임
    """
    logger.debug(f"식재료 상품 추천 시작: user_id={current_user.user_id}, ingredient={ingredient}")
    logger.info(f"식재료 상품 추천 API 호출: user_id={current_user.user_id}, ingredient={ingredient}")
    
    try:
        # 상품 추천 로직 실행 (SQLAlchemy 세션 사용)
        recommendations = await recommend_for_ingredient(db, ingredient, max_total=5, max_home=2)
        logger.debug(f"식재료 상품 추천 성공: ingredient={ingredient}, 추천 상품 수={len(recommendations)}, user_id={current_user.user_id}")
        
        # 상품 추천 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="ingredient_product_recommend", 
                event_data={
                    "ingredient": ingredient,
                    "recommendation_count": len(recommendations)
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"식재료 상품 추천 완료: ingredient={ingredient}, 추천 상품 수={len(recommendations)}, user_id={current_user.user_id}")
        
        return ProductRecommendResponse(
            ingredient=ingredient,
            recommendations=recommendations,
            total_count=len(recommendations)
        )
        
    except Exception as e:
        logger.error(f"식재료 상품 추천 실패: ingredient={ingredient}, user_id={current_user.user_id}, error={e}")
        raise HTTPException(
            status_code=500, 
            detail="상품 추천 중 오류가 발생했습니다."
        )



# ML 서비스 설정 로드
# ============================================================================
# KOK 홈쇼핑 추천 로직 (kok_homeshopping.py에서 이식) - 주석 처리
# ============================================================================
#
# # -------------------- 동적 파라미터 --------------------
# def _env_int(key: str, default: int) -> int:
#     try:
#         return int(os.getenv(key, str(default)))
#     except Exception:
#         return default
#
# # LIKE 검색/키워드 확장 파라미터(외부에서도 import해 사용)
# DYN_MAX_TERMS   = _env_int("DYN_MAX_TERMS", 32)
# DYN_MAX_EXTRAS  = _env_int("DYN_MAX_EXTRAS", 20)
# DYN_SAMPLE_ROWS = _env_int("DYN_SAMPLE_ROWS", 4000)
#
# # Tail / n-gram 필터 동작 파라미터
# TAIL_MAX_DF_RATIO = float(os.getenv("TAIL_MAX_DF_RATIO", "0.35"))  # 희소 토큰 판정 기준(문서비율 ≤ 0.35)
# TAIL_MAX_TERMS    = _env_int("TAIL_MAX_TERMS", 3)                   # tail 후보로 쓸 최대 토큰 수
# NGRAM_N           = _env_int("NGRAM_N", 2)                          # bi-gram 기본
#
# # n-gram 생성 범위
# DYN_NGRAM_MIN  = _env_int("DYN_NGRAM_MIN", 2)
# DYN_NGRAM_MAX  = max(DYN_NGRAM_MIN, _env_int("DYN_NGRAM_MAX", 4))
#
# # (참고용) 선택 규칙/카운트 범위가 필요하면 여기에 추가해 사용
# DYN_COUNT_MIN  = _env_int("DYN_COUNT_MIN", 3)
# DYN_COUNT_MAX  = _env_int("DYN_COUNT_MAX", 30000)
#
# # -------------------- 사전/패턴 --------------------
# DEFAULT_STOPWORDS: Set[str] = set("""
# 세트 선물세트 모음 모음전 구성 증정 행사 정품 정기 무료 특가 사은품 선물 혼합 혼합세트 묶음 총 택
# 옵션 국내산 수입산 무료배송 당일 당일발송 예약 신상 히트 인기 추천 기획 기획세트 명품 프리미엄 리미티드
# 한정 본품 리뉴얼 정가 정상가 행사상품 대용량 소용량 박스 리필 업소용 가정용 편의점 오리지널 리얼 신제품 공식 단독
# 정기구독 구독 사은 혜택 특전 한정판 고당도 산지 당일 당일직송 직송 손질 세척 냉동 냉장 생물 해동 숙성
# 팩 봉 포 개 입 병 캔 스틱 정 포기 세트구성 골라담기 택1 택일 실속 못난이 파우치 슬라이스 인분 종
# """.split())
#
# DEFAULT_ROOT_HINTS = [
#     "육수","다시","사골","곰탕","장국","티백","멸치","황태","디포리","가쓰오","가다랭이",
#     "주꾸미","쭈꾸미","오징어","한치","문어","낙지","새우","꽃게","홍게","대게","게",
#     "김치","포기김치","열무김치","갓김치","동치미","만두","교자","왕교자","라면","우동","국수","칼국수","냉면",
#     "사리","메밀","막국수","어묵","오뎅","두부","순두부","유부","우유","치즈","요거트","버터",
#     "닭","닭가슴살","닭다리","닭안심","돼지","돼지고기","삼겹살","목살","소고기","한우","양지","사태","갈비","차돌",
#     "식용유","참기름","들기름","설탕","소금","고추장","된장","간장","쌈장","고춧가루","카레","짜장","분말",
#     "명란","명란젓","젓갈","어란","창란","창란젓","오징어젓","낙지젓",
# ]
# DEFAULT_STRONG_NGRAMS = ["사골곰탕","포기김치","왕교자","어묵탕","갈비탕","육개장","사골국물","황태채","국물티백"]
# DEFAULT_VARIANTS = {
#     "주꾸미": ["쭈꾸미"],
#     "가쓰오": ["가츠오","가쓰오부시","가츠오부시"],
#     "명태":   ["북어"],
#     "어묵":   ["오뎅"],
#     "백명란": ["명란","명란젓"],
# }
#
# _MEAS1   = re.compile(r"\d+(?:\.\d+)?\s*(?:g|kg|ml|l|L)?\s*(?:[xX×＊*]\s*\d+)?", re.I)
# _MEAS2   = re.compile(r"\b\d+[a-zA-Z]+\b")
# _ONLYNUM = re.compile(r"\b\d+\b")
# _HANGUL_ONLY = re.compile(r"^[가-힣]{2,}$")
#
# def _load_yaml(path: str) -> dict:
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             return yaml.safe_load(f) or {}
#     except Exception:
#         return {}
#
# def load_domain_dicts() -> Dict:
#     """CATEGORY_DICT_PATH/KEYWORDS_DICT_PATH가 있으면 결합하여 로딩."""
#     cat_path = os.getenv("CATEGORY_DICT_PATH", "").strip()
#     key_path = os.getenv("KEYWORDS_DICT_PATH", "").strip()
#
#     roots = set(DEFAULT_ROOT_HINTS)
#     strong = set(DEFAULT_STRONG_NGRAMS)
#     variants = {k:list(v) for k,v in DEFAULT_VARIANTS.items()}
#     stopwords = set(DEFAULT_STOPWORDS)
#
#     if cat_path and os.path.exists(cat_path):
#         cat = _load_yaml(cat_path)
#         for _, rule in (cat.get("categories") or {}).items():
#             detect = rule.get("detect") or rule.get("match") or []
#             like   = rule.get("candidate_like") or rule.get("like_extra") or []
#             excl   = rule.get("exclude") or []
#             roots.update(detect); roots.update(like); stopwords.update(excl)
#
#     if key_path and os.path.exists(key_path):
#         kd = _load_yaml(key_path)
#         roots.update(kd.get("roots", []) or [])
#         strong.update(kd.get("strong_ngrams", []) or [])
#         stopwords.update(kd.get("stopwords", []) or [])
        # for k, arr in (kd.get("variants") or {}).items():
        #     vs = variants.get(k, [])
        #     for v in arr or []:
        #         if v not in vs: vs.append(v)
        #     variants[k] = vs
#
#     return {
#         "roots": sorted(roots, key=len, reverse=True),
#         "strong_ngrams": sorted(strong, key=len, reverse=True),
#         "variants": variants,
#         "stopwords": stopwords,
#     }
#
# # -------------------- 전처리/토큰화 --------------------
# def normalize_name(name: str) -> str:
#     if not isinstance(name, str):
#         return ""
#     s = re.sub(r"\[[^\]]*\]", " ", name)
#     s = re.sub(r"\([^)]*\)", " ", s)
#     s = _MEAS1.sub(" ", s); s = _MEAS2.sub(" ", s); s = _ONLYNUM.sub(" ", s)
#     s = re.sub(r"[^\w가-힣]+", " ", s)
#     s = re.sub(r"\s+", " ", s).strip()
#     return s
#
# def tokenize_normalized(text: str, stopwords: Set[str]) -> List[str]:
#     s = normalize_name(text)
#     return [t for t in s.split() if len(t) >= 2 and not t.isnumeric() and t not in stopwords]
#
# def _split_by_roots(token: str, roots: List[str]) -> List[str]:
#     return [r for r in roots if r and r in token and token != r]
#
# def _expand_variants(core: List[str], variants: Dict[str, List[str]]) -> List[str]:
#     out: List[str] = []
#     seen = set()
#     for k in core:
#         if k not in seen:
#             out.append(k); seen.add(k)
#         for v in variants.get(k, []):
#             if v not in seen:
#                 out.append(v); seen.add(v)
#     return out
#
# # -------------------- 핵심/루트/테일 키워드 --------------------
# def extract_core_keywords(prod_name: str, max_n: int = 3) -> List[str]:
#     d = load_domain_dicts()
#     roots, strong, variants, stop = d["roots"], d["strong_ngrams"], d["variants"], d["stopwords"]
#
#     s = normalize_name(prod_name)
#     found_ng = [ng for ng in strong if ng and ng in s]
#     raw_toks = tokenize_normalized(s, stop)
#
#     expanded: List[str] = []
#     for t in raw_toks:
#         expanded.extend(_split_by_roots(t, roots))
#         expanded.append(t)
#
#     ordered: List[str] = []
#     for ng in found_ng:
#         if ng not in ordered: ordered.append(ng)
#         for r in _split_by_roots(ng, roots):
#             if r not in ordered: ordered.append(r)
#     for t in expanded:
#         if t not in ordered: ordered.append(t)
#
#     core = ordered[:max_n]
#     return _expand_variants(core, variants)[:max_n]
#
# def roots_in_name(prod_name: str) -> List[str]:
#     d = load_domain_dicts()
#     s = normalize_name(prod_name)
#     hits = [r for r in d["roots"] if len(r) >= 2 and (r in s) and (r not in d["stopwords"])]
#     # 중복 제거 순서 보존
#     out = []
#     seen = set()
#     for h in hits:
#         if h not in seen:
#             out.append(h); seen.add(h)
#     return out[:5]
#
# def extract_tail_keywords(prod_name: str, max_n: int = 2) -> List[str]:
#     """뒤쪽 핵심 키워드 중심으로(희소성/변형 고려는 가볍게) 추출."""
#     d = load_domain_dicts()
#     stop, variants, roots = d["stopwords"], d["variants"], d["roots"]
#     s = normalize_name(prod_name)
#     toks = [t for t in s.split() if len(t) >= 2 and not t.isnumeric() and t not in stop and not re.search(r"\d", t)]
#
#     tail_base: List[str] = []
#     for t in reversed(toks):
#         if t not in tail_base:
#             tail_base.append(t)
#         if len(tail_base) >= max_n:
#             break
#     tail_base.reverse()
#
#     expanded = list(tail_base)
#     for t in tail_base:
#         for v in variants.get(t, []):
#             if v not in expanded:
#                 expanded.append(v)
#     for t in tail_base:
#         for r in _split_by_roots(t, roots):
#             if r not in expanded:
#                 expanded.append(r)
#     return expanded
#
# # -------------------- 동적 n-gram --------------------
# def _char_ngrams_windowed(token: str, nmin: int, nmax: int) -> List[str]:
#     out = []
#     L = len(token)
#     for n in range(nmin, min(nmax, L) + 1):
#         for i in range(0, L - n + 1):
#             out.append(token[i:i+n])
#     return out
#
# def infer_terms_from_name_via_ngrams(prod_name: str, max_terms: int = DYN_MAX_TERMS) -> List[str]:
#     d = load_domain_dicts()
#     stop = d["stopwords"]
#
#     toks = tokenize_normalized(prod_name, stop)
#     toks = [t for t in toks if _HANGUL_ONLY.fullmatch(t)]
#
#     cand = []
#     for t in toks:
#         cand.extend(_char_ngrams_windowed(t, DYN_NGRAM_MIN, DYN_NGRAM_MAX))
#     cand.extend([t for t in toks if len(t) >= DYN_NGRAM_MIN])
#
#     cand = [c for c in cand if _HANGUL_ONLY.fullmatch(c) and c not in stop]
#     cand = list(dict.fromkeys(cand))[:max_terms]
#     return cand
#
# # -------------------- tail + n-gram AND 필터 --------------------
# def _char_ngrams_raw(s: str, n: int = 2) -> Set[str]:
#     s2 = normalize_name(s).replace(" ", "")
#     if len(s2) < n:
#         return set()
#     return {s2[i:i+n] for i in range(len(s2)-n+1)}
#
# def _ngram_overlap_count(a: str, b: str, n: int = 2) -> int:
#     return len(_char_ngrams_raw(a, n) & _char_ngrams_raw(b, n))
#
# def _dynamic_tail_terms(query_name: str, candidate_names: List[str], stopwords: Set[str]) -> List[str]:
#     """후보 집합에서 희소한 쿼리 토큰만 tail로 선정."""
#     q_toks = set(tokenize_normalized(query_name, stopwords))
#     if not q_toks or not candidate_names:
#         return list(q_toks)[:1]  # 폴백
#
#     df = Counter()
#     for name in candidate_names:
#         df.update(set(tokenize_normalized(name, stopwords)))
#
#     total_docs = max(1, len(candidate_names))
#     tail = [t for t in q_toks if (df.get(t, 0) / total_docs) <= TAIL_MAX_DF_RATIO]
#     tail.sort(key=lambda t: df.get(t, 0))  # 희소한 순
#     if not tail:
#         tail = list(q_toks)[:1]
#     return tail[:max(1, TAIL_MAX_TERMS)]
#
# def filter_tail_and_ngram_and(details: List[dict], prod_name: str) -> List[dict]:
#     """
#     AND 조건:
#       - tail 토큰 일치 ≥ 1
#       - n-gram 겹침 ≥ 1 (기본 bi-gram)
#     들어온 순서를 보존(이미 정렬되어 있다고 가정).
#     """
#     if not details:
#         return []
#     d = load_domain_dicts()
#     stop = d["stopwords"]
#
#     cand_names = [f"{r.get('KOK_PRODUCT_NAME','')} {r.get('KOK_STORE_NAME','')}" for r in details]
#     tails = set(_dynamic_tail_terms(prod_name, cand_names, stop))
#
#     out = []
#     for r in details:
#         name = f"{r.get('KOK_PRODUCT_NAME','')} {r.get('KOK_STORE_NAME','')}"
#         toks = set(tokenize_normalized(name, stop))
#         tail_hits = len(tails & toks)
#         ngram_hits = _ngram_overlap_count(prod_name, name, n=NGRAM_N)
#         if tail_hits >= 1 and ngram_hits >= 1:
#             out.append(r)
#     return out
#
# # -------------------- 마지막 의미 토큰 추출 --------------------
# def last_meaningful_token(text: str) -> str:
#     """
#     정규화 + stopwords 기반 토크나이즈 후,
#     포장/수량성 토큰(종, 세트, 팩 등)은 건너뛰고 마지막 의미 토큰을 반환.
#     """
#     d = load_domain_dicts()
#     stop = d["stopwords"]
#     toks = tokenize_normalized(text, stop)
#
#     # 마지막 위치에서부터 의미 토큰만 선택
#     SKIP_LAST = {
#         "종", "세트", "세트구성", "박스", "구성", "혼합", "모음", "모음전", "구독",
#         "택", "택일", "포기", "인분",
#         "팩", "봉", "포", "입", "병", "캔", "스틱", "정",
#         "대용량", "소용량"
#     }
#     for t in reversed(toks):
#         if t not in SKIP_LAST:
#             return t
#     return ""  # 전부 스킵되면 빈 문자열 반환
#
# # -------------------- 추천 전략 --------------------
# def recommend_by_last_word(kok_product_name: str, k: int = 5) -> List[str]:
#     """마지막 의미 토큰 기반 추천"""
#     last = last_meaningful_token(kok_product_name)
#     if not last:
#         return []
#    
#     # 마지막 토큰이 포함된 검색어 반환
#     return [last]
#
# def recommend_by_core_keywords(kok_product_name: str, k: int = 5) -> List[str]:
#     """핵심 키워드 기반 추천"""
#     core_keywords = extract_core_keywords(kok_product_name, max_n=k)
#     return core_keywords
#
# def recommend_by_tail_keywords(kok_product_name: str, k: int = 5) -> List[str]:
#     """Tail 키워드 기반 추천"""
#     tail_keywords = extract_tail_keywords(kok_product_name, max_n=k)
#     return tail_keywords
#
# def get_recommendation_strategy(kok_product_name: str, k: int = 5) -> Dict[str, Any]:
#     """추천 전략 선택 및 실행"""
#     if not kok_product_name:
#         return {
#             "algorithm": "none",
#             "status": "failed",
#             "search_terms": [],
#             "message": "상품명이 없습니다."
#         }
#    
#     # 1. 마지막 의미 토큰 전략
#     last_word_results = recommend_by_last_word(kok_product_name, k)
#     if last_word_results:
#         return {
#             "algorithm": "last_meaningful_token",
#             "status": "success",
#             "search_terms": last_word_results,
#             "message": "마지막 의미 토큰 기반 추천"
#         }
#    
#     # 2. 핵심 키워드 전략
#     core_results = recommend_by_core_keywords(kok_product_name, k)
#     if core_results:
#         return {
#             "algorithm": "core_keywords",
#             "status": "success",
#             "search_terms": core_results,
#             "message": "핵심 키워드 기반 추천"
#         }
#    
#     # 3. Tail 키워드 전략
#     tail_results = recommend_by_tail_keywords(kok_product_name, k)
#     if tail_results:
#         return {
#             "algorithm": "tail_keywords",
#             "status": "success",
#             "search_terms": tail_results,
#             "message": "Tail 키워드 기반 추천"
#         }
#    
#     # 4. 폴백: 상품명의 일부 사용
#     normalized = normalize_name(kok_product_name)
#     tokens = tokenize_normalized(normalized, DEFAULT_STOPWORDS)
#     if tokens:
#         return {
#             "algorithm": "fallback_tokens",
#             "status": "success",
#             "search_terms": tokens[:k],
#             "message": "폴백 토큰 기반 추천"
#         }
#    
#     return {
#         "algorithm": "none",
#         "status": "failed",
#         "search_terms": [],
#         "message": "적절한 추천 전략을 찾을 수 없습니다."
#     }

# ============================================================================
# 주석 처리된 기존 API들 (참고용)
# ============================================================================

# @router.get("/kok")
# async def get_kok_products(
#     ingredient: str = Query(..., description="검색할 식재료명(예: 감자, 양파 등)"),
#     current_user = Depends(get_current_user),
#     background_tasks: BackgroundTasks = None,
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     콕 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
#     - 반환 필드명은 kok 모델 변수명(소문자)과 100% 일치
#     """
#     logger.info(f"콕 상품 검색 API 호출: user_id={current_user.user_id}, ingredient={ingredient}")
#     products = await get_kok_products_by_ingredient(db, ingredient)
    
#     # 식재료 기반 상품 검색 로그 기록
#     if background_tasks:
#         background_tasks.add_task(
#             send_user_log, 
#             user_id=current_user.user_id, 
#             event_type="ingredient_product_search", 
#             event_data={
#                 "ingredient": ingredient,
#                 "product_count": len(products)
#             }
#         )
    
#     return products

# @router.get("/homeshopping", response_model=HomeshoppingProductsResponse)
# async def get_homeshopping_products(
#     ingredient: str = Query(..., description="검색할 식재료명(예: 감자, 양파 등)"),
#     current_user = Depends(get_current_user),
#     background_tasks: BackgroundTasks = None,
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     재료와 관련된 홈쇼핑 내 관련 상품 정보(상품이미지, 상품명, 브랜드명, 가격)를 조회한다.
#     """
#     logger.info(f"홈쇼핑 상품 검색 API 호출: user_id={current_user.user_id}, ingredient={ingredient}")
    
#     try:
#         products = await get_homeshopping_products_by_ingredient(db, ingredient)
        
#         # 홈쇼핑 상품 검색 로그 기록
#         if background_tasks:
#             background_tasks.add_task(
#                 send_user_log, 
#                 user_id=current_user.user_id, 
#                 event_type="homeshopping_product_search", 
#                 event_data={
#                     "ingredient": ingredient,
#                     "product_count": len(products)
#                 }
#             )
        
#         logger.info(f"홈쇼핑 상품 검색 완료: ingredient={ingredient}, 상품 개수={len(products)}")
        
#         return {
#             "ingredient": ingredient,
#             "products": products,
#             "total_count": len(products)
#         }
        
#     except Exception as e:
#         logger.error(f"홈쇼핑 상품 검색 실패: ingredient={ingredient}, user_id={current_user.user_id}, error={e}")
#         raise HTTPException(
#             status_code=500, 
#             detail="홈쇼핑 상품 검색 중 오류가 발생했습니다."
#         )

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
