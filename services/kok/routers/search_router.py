from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user, get_current_user_optional
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.user.schemas.profile_schema import UserOut
from services.kok.schemas.interaction_schema import (
    KokSearchResponse,
    KokSearchHistoryResponse,
    KokSearchHistoryCreate,
    KokSearchHistoryDeleteResponse,
)
from services.kok.crud.search_crud import (
    search_kok_products,
    get_kok_search_history,
    add_kok_search_history,
    delete_kok_search_history,
)

logger = get_logger("kok_router")
router = APIRouter()

@router.get("/search", response_model=KokSearchResponse)
async def search_products(
    request: Request,
    keyword: str = Query(..., description="검색 키워드"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    키워드 기반으로 콕 쇼핑몰 내에 있는 상품을 검색
    """
    logger.debug(f"상품 검색 시작: keyword='{keyword}', page={page}, size={size}")
    
    try:
        current_user = await get_current_user_optional(request)
        user_id = current_user.user_id if current_user else None
        
        if not current_user:
            logger.warning(f"인증되지 않은 사용자가 상품 검색 요청: keyword='{keyword}'")
        
        logger.info(f"상품 검색 요청: user_id={user_id}, keyword='{keyword}', page={page}, size={size}")
        
        products, total = await search_kok_products(db, keyword, page, size)
        logger.debug(f"상품 검색 성공: keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
        logger.info(f"상품 검색 완료: user_id={user_id}, keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
        
        # 인증된 사용자의 경우에만 로그 기록과 검색 기록 저장
        if current_user and background_tasks:
            # 검색 로그 기록
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_product_search", 
                event_data={"keyword": keyword, "result_count": len(products)},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
            
            # 검색 기록 저장
            background_tasks.add_task(
                add_kok_search_history,
                db=db,
                user_id=current_user.user_id,
                keyword=keyword
            )
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "products": products
        }
        
    except Exception as e:
        logger.error(f"상품 검색 API 오류: keyword='{keyword}', user_id={user_id}, error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"상품 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/search/history", response_model=KokSearchHistoryResponse)
async def get_search_history(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="조회할 이력 개수"),
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 조회
    """
    logger.debug(f"검색 이력 조회 시작: user_id={current_user.user_id}, limit={limit}")
    
    try:
        history = await get_kok_search_history(db, current_user.user_id, limit)
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
            event_type="kok_search_history_view", 
            event_data={"history_count": len(history)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return {"history": history}


@router.post("/search/history", response_model=dict)
async def add_search_history(
    request: Request,
    search_data: KokSearchHistoryCreate,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 저장
    """
    logger.debug(f"검색 이력 추가 시작: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    logger.info(f"검색 이력 추가 요청: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    
    try:
        saved_history = await add_kok_search_history(db, current_user.user_id, search_data.keyword)
        await db.commit()
        logger.debug(f"검색 이력 추가 성공: user_id={current_user.user_id}, history_id={saved_history['kok_history_id']}")
        logger.info(f"검색 이력 추가 완료: user_id={current_user.user_id}, history_id={saved_history['kok_history_id']}")
        
        # 검색 이력 저장 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_search_history_save", 
                event_data={"keyword": search_data.keyword},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return {
            "message": "검색 이력이 저장되었습니다.",
            "saved": saved_history
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"검색 이력 추가 실패: user_id={current_user.user_id}, keyword='{search_data.keyword}', error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 저장 중 오류가 발생했습니다.")


@router.delete("/search/history/{history_id}", response_model=KokSearchHistoryDeleteResponse)
async def delete_search_history(
    request: Request,
    history_id: int,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    사용자의 검색 이력을 삭제
    """
    logger.debug(f"검색 이력 삭제 시작: user_id={current_user.user_id}, history_id={history_id}")
    logger.info(f"검색 이력 삭제 요청: user_id={current_user.user_id}, history_id={history_id}")
    
    try:
        deleted = await delete_kok_search_history(db, current_user.user_id, history_id)
        
        if deleted:
            await db.commit()
            logger.debug(f"검색 이력 삭제 성공: user_id={current_user.user_id}, history_id={history_id}")
            logger.info(f"검색 이력 삭제 완료: user_id={current_user.user_id}, history_id={history_id}")
            
            # 검색 이력 삭제 로그 기록
            if background_tasks:
                http_info = extract_http_info(request, response_code=200)
                background_tasks.add_task(
                    send_user_log, 
                    user_id=current_user.user_id, 
                    event_type="kok_search_history_delete", 
                    event_data={"history_id": history_id},
                    **http_info  # HTTP 정보를 키워드 인자로 전달
                )
            
            return {"message": f"검색 이력 ID {history_id}가 삭제되었습니다."}
        else:
            logger.warning(f"검색 이력을 찾을 수 없음: user_id={current_user.user_id}, history_id={history_id}")
            raise HTTPException(status_code=404, detail="해당 검색 이력을 찾을 수 없습니다.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"검색 이력 삭제 실패: user_id={current_user.user_id}, history_id={history_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 삭제 중 오류가 발생했습니다.")
