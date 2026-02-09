from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user_optional
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.kok.schemas.product_schema import (
    KokProductInfoResponse,
    KokProductTabsResponse,
    KokReviewResponse,
    KokProductDetailsResponse,
)
from services.kok.crud.product_crud import (
    get_kok_product_info,
    get_kok_product_tabs,
    get_kok_review_data,
    get_kok_product_seller_details,
)

logger = get_logger("kok_router")
router = APIRouter()

@router.get("/product/{kok_product_id}/info", response_model=KokProductInfoResponse)
async def get_product_info(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 기본 정보 조회
    """
    logger.debug(f"상품 기본 정보 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 기본 정보 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 기본 정보 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        product = await get_kok_product_info(db, kok_product_id, user_id)
        if not product:
            logger.warning(f"상품을 찾을 수 없음: kok_product_id={kok_product_id}, user_id={user_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 기본 정보 조회 성공: kok_product_id={kok_product_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 기본 정보 조회 실패: kok_product_id={kok_product_id}, user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 기본 정보 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_info_view", 
            event_data={"kok_product_id": kok_product_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 기본 정보 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return product


@router.get("/product/{kok_product_id}/tabs", response_model=KokProductTabsResponse)
async def get_product_tabs(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 설명 탭 정보 조회
    """
    logger.debug(f"상품 탭 정보 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 탭 정보 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 탭 정보 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        images_response = await get_kok_product_tabs(db, kok_product_id)
        if images_response is None:
            logger.warning(f"상품 탭 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 탭 정보 조회 성공: kok_product_id={kok_product_id}, 탭 수={len(images_response.images)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 탭 정보 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 탭 정보 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_tabs_view", 
            event_data={"kok_product_id": kok_product_id, "tab_count": len(images_response.images)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 탭 정보 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return images_response


@router.get("/product/{kok_product_id}/reviews", response_model=KokReviewResponse)
async def get_product_reviews(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 리뷰 탭 정보 조회
    - KOK_PRODUCT_INFO 테이블에서 리뷰 통계 정보
    - KOK_REVIEW_EXAMPLE 테이블에서 개별 리뷰 목록
    """
    logger.debug(f"상품 리뷰 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 리뷰 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 리뷰 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        review_data = await get_kok_review_data(db, kok_product_id)
        if review_data is None:
            logger.warning(f"상품 리뷰 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 리뷰 조회 성공: kok_product_id={kok_product_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 리뷰 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 리뷰 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_reviews_view", 
            event_data={"kok_product_id": kok_product_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 리뷰 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return review_data


# ================================
# 제품 상세 정보
# ================================

@router.get("/product/{kok_product_id}/seller-details", response_model=KokProductDetailsResponse)
async def get_product_details(
        request: Request,
        kok_product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    상품 판매자 정보 및 상세정보 조회
    """
    logger.debug(f"상품 상세 정보 조회 시작: kok_product_id={kok_product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 상세 정보 조회 요청: kok_product_id={kok_product_id}")
    
    logger.info(f"상품 상세 정보 조회 요청: user_id={user_id}, kok_product_id={kok_product_id}")
    
    try:
        product_details = await get_kok_product_seller_details(db, kok_product_id)
        if not product_details:
            logger.warning(f"상품 상세 정보를 찾을 수 없음: kok_product_id={kok_product_id}")
            raise HTTPException(status_code=404, detail="상품이 존재하지 않습니다.")
        logger.debug(f"상품 상세 정보 조회 성공: kok_product_id={kok_product_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 상세 정보 조회 실패: kok_product_id={kok_product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 상세 정보 조회 중 오류가 발생했습니다.")
    
    # 인증된 사용자의 경우에만 로그 기록
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="kok_product_details_view", 
            event_data={"kok_product_id": kok_product_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"상품 상세 정보 조회 완료: user_id={user_id}, kok_product_id={kok_product_id}")
    return product_details
