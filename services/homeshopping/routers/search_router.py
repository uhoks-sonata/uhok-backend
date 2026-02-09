from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user, get_current_user_optional
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.search_crud import (
    add_homeshopping_search_history,
    delete_homeshopping_search_history,
    get_homeshopping_search_history,
    search_homeshopping_products,
)
from services.homeshopping.schemas.search_schema import (
    HomeshoppingSearchHistoryCreate,
    HomeshoppingSearchHistoryDeleteRequest,
    HomeshoppingSearchHistoryDeleteResponse,
    HomeshoppingSearchHistoryResponse,
    HomeshoppingSearchResponse,
)
from services.user.schemas.profile_schema import UserOut

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()

@router.get("/search", response_model=HomeshoppingSearchResponse)
async def search_products(
        request: Request,
        keyword: str = Query(..., description="검색 키워드"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 검색
    """
    logger.debug(f"홈쇼핑 상품 검색 시작: keyword='{keyword}'")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 상품 검색 요청: keyword='{keyword}'")
    
    logger.info(f"홈쇼핑 상품 검색 요청: user_id={user_id}, keyword='{keyword}'")
    
    try:
        products = await search_homeshopping_products(db, keyword)
        logger.debug(f"상품 검색 성공: keyword='{keyword}', 결과 수={len(products)}")
    except Exception as e:
        logger.error(f"상품 검색 실패: keyword='{keyword}', error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 검색 중 오류가 발생했습니다.")
    
    # 검색 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search", 
            event_data={"keyword": keyword},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 상품 검색 완료: user_id={user_id}, keyword='{keyword}', 결과 수={len(products)}")
    return {
        "total": len(products),
        "page": 1,
        "size": len(products),
        "products": products
    }


# ================================
# 검색 이력 관련 API
# ================================

@router.post("/search/history", response_model=dict)
async def add_search_history(
        request: Request,
        search_data: HomeshoppingSearchHistoryCreate,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 저장
    """
    logger.debug(f"홈쇼핑 검색 이력 저장 시작: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    logger.info(f"홈쇼핑 검색 이력 저장 요청: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    
    try:
        saved_history = await add_homeshopping_search_history(db, current_user.user_id, search_data.keyword)
        await db.commit()
        logger.debug(f"검색 이력 저장 성공: history_id={saved_history['homeshopping_history_id']}")
        
        # 검색 이력 저장 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_search_history_save", 
                event_data={"keyword": search_data.keyword},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 검색 이력 저장 완료: user_id={current_user.user_id}, history_id={saved_history['homeshopping_history_id']}")
        return saved_history
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 검색 이력 저장 실패: user_id={current_user.user_id}, keyword='{search_data.keyword}', error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 저장 중 오류가 발생했습니다.")


@router.get("/search/history", response_model=HomeshoppingSearchHistoryResponse)
async def get_search_history(
        request: Request,
        limit: int = Query(5, ge=1, le=20, description="조회할 검색 이력 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 조회
    """
    logger.debug(f"홈쇼핑 검색 이력 조회 시작: user_id={current_user.user_id}, limit={limit}")
    logger.info(f"홈쇼핑 검색 이력 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    try:
        history = await get_homeshopping_search_history(db, current_user.user_id, limit)
        logger.debug(f"검색 이력 조회 성공: user_id={current_user.user_id}, 결과 수={len(history)}")
    except Exception as e:
        logger.error(f"검색 이력 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 조회 중 오류가 발생했습니다.")
    
    # 검색 이력 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search_history_view", 
            event_data={"history_count": len(history)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 검색 이력 조회 완료: user_id={current_user.user_id}, 결과 수={len(history)}")
    return {"history": history}


@router.delete("/search/history", response_model=HomeshoppingSearchHistoryDeleteResponse)
async def delete_search_history(
        request: Request,
        delete_data: HomeshoppingSearchHistoryDeleteRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 삭제
    """
    logger.debug(f"홈쇼핑 검색 이력 삭제 시작: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
    logger.info(f"홈쇼핑 검색 이력 삭제 요청: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
    
    try:
        success = await delete_homeshopping_search_history(db, current_user.user_id, delete_data.homeshopping_history_id)
        
        if not success:
            logger.warning(f"삭제할 검색 이력을 찾을 수 없음: history_id={delete_data.homeshopping_history_id}")
            raise HTTPException(status_code=404, detail="삭제할 검색 이력을 찾을 수 없습니다.")
        
        await db.commit()
        logger.debug(f"검색 이력 삭제 성공: history_id={delete_data.homeshopping_history_id}")
        
        # 검색 이력 삭제 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_search_history_delete", 
                event_data={"history_id": delete_data.homeshopping_history_id},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
        return {"message": "검색 이력이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 검색 이력 삭제 실패: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 삭제 중 오류가 발생했습니다.")

