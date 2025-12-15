"""
레시피 상세/재료/만개의레시피 url, 후기, 별점 API 라우터 (MariaDB)
- HTTP 요청/응답을 담당
- 파라미터 파싱, 유저 인증/권한 확인, 의존성 주입 (Depends)
- 비즈니스 로직은 호출만 하고 직접 DB 처리(트랜잭션)는 하지 않음
- 트랜잭션 관리(commit/rollback)를 담당
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, Path, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
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
    search_recipes_with_pagination,
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
            df, total_approx, has_more = await search_recipes_with_pagination(
                mariadb=mariadb,
                method=method,
                recipe=recipe,
                page=page,
                size=size,
                result_ids=result_ids,
            )

        except Exception as e:
            logger.error(f"ML 서비스 기반 레시피 검색 실패: user_id={current_user.user_id}, keyword={recipe}, error={str(e)}")
            raise HTTPException(status_code=500, detail="레시피 검색 중 오류가 발생했습니다.")

    else: # method == "ingredient"
        # 기존 재료 검색 로직 유지
        df, total_approx, has_more = await search_recipes_with_pagination(
            mariadb=mariadb,
            method=method,
            recipe=recipe,
            page=page,
            size=size,
            result_ids=None,
        )
        if df.empty:
            return {"recipes": [], "page": page, "total": total_approx}

    # 페이지네이션 및 결과 포맷팅
    start_index = (page - 1) * size
    page_df = df.iloc[:size] if not df.empty else df
    # total_approx와 has_more는 crud 함수에서 계산된 값을 사용

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
