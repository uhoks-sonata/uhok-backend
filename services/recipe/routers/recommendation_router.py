"""Recipe recommendation endpoints."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.recipe.crud.recipe_recommendation_crud import (
    recommend_recipes_combination_1,
    recommend_recipes_combination_2,
    recommend_recipes_combination_3,
)
from services.recipe.schemas.recipe_recommendation_schema import RecipeByIngredientsListResponse
from services.recipe.utils.combination_tracker import CombinationTracker
from services.recipe.utils.simple_cache import recipe_cache

router = APIRouter()
logger = get_logger("recipe_router")
combination_tracker = CombinationTracker()

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
