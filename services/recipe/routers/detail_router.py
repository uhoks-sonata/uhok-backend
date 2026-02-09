"""Recipe detail endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.recipe.crud.recipe_detail_crud import get_recipe_detail
from services.recipe.utils.inventory_recipe import get_recipe_url
from services.recipe.schemas.recipe_core_schema import RecipeDetailResponse, RecipeUrlResponse

router = APIRouter()
logger = get_logger("recipe_router")

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
