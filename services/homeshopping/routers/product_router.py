from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user_optional
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.product_crud import get_homeshopping_product_detail
from services.homeshopping.schemas.product_schema import HomeshoppingProductDetailResponse

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()

@router.get("/product/{live_id}", response_model=HomeshoppingProductDetailResponse)
async def get_product_detail(
        request: Request,
        live_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 상세 조회
    """
    logger.debug(f"홈쇼핑 상품 상세 조회 시작: live_id={live_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 상세 조회 요청: live_id={live_id}")
    
    logger.info(f"홈쇼핑 상품 상세 조회 요청: user_id={user_id}, live_id={live_id}")
    
    try:
        product_detail = await get_homeshopping_product_detail(db, live_id, user_id)
        if not product_detail:
            logger.warning(f"상품을 찾을 수 없음: live_id={live_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        logger.debug(f"상품 상세 정보 조회 성공: live_id={live_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 상세 조회 실패: live_id={live_id}, user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 상세 조회 중 오류가 발생했습니다.")
    
    # 상품 상세 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_product_detail_view", 
            event_data={"live_id": live_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 상품 상세 조회 완료: user_id={user_id}, live_id={live_id}")
    return product_detail
