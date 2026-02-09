"""Recipe ingredient-status endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.recipe.crud.recipe_ingredient_status_crud import get_recipe_ingredients_status
from services.recipe.schemas.recipe_ingredient_status_schema import RecipeIngredientStatusResponse
from services.user.schemas.profile_schema import UserOut

router = APIRouter()
logger = get_logger("recipe_router")

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

