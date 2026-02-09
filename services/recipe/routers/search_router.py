"""Recipe search endpoints."""

import time

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.recipe.crud.recipe_search_crud import search_recipes_with_pagination
from services.recipe.utils.remote_ml_adapter import _call_ml_search_service

load_dotenv()

router = APIRouter()
logger = get_logger("recipe_router")

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
