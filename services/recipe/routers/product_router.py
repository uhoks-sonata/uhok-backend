"""Recipe product recommendation endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.recipe.schemas.recipe_recommendation_schema import ProductRecommendResponse
from services.recipe.utils.product_recommend import recommend_for_ingredient
from services.user.schemas.profile_schema import UserOut

router = APIRouter()
logger = get_logger("recipe_router")

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
