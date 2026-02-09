"""Recipe rating endpoints."""

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.recipe.crud.recipe_rating_crud import get_recipe_rating, set_recipe_rating
from services.recipe.schemas.recipe_rating_schema import RecipeRatingCreate, RecipeRatingResponse
from services.user.schemas.profile_schema import UserOut

router = APIRouter()
logger = get_logger("recipe_router")

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
