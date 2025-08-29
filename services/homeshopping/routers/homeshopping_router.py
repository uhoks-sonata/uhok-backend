"""
홈쇼핑 API 라우터 (MariaDB)
- 편성표 조회, 상품 검색, 찜 기능, 주문 등 홈쇼핑 관련 기능

계층별 역할:
- 이 파일은 API 라우터 계층을 담당
- HTTP 요청/응답 처리, 파라미터 파싱, 유저 인증/권한 확인
- 비즈니스 로직은 CRUD 함수 호출만 하고 직접 DB 처리하지 않음
- 트랜잭션 관리(commit/rollback)를 담당하여 데이터 일관성 보장
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from typing import Optional
from datetime import date

from common.dependencies import get_current_user, get_current_user_optional

from services.user.schemas.user_schema import UserOut
from services.homeshopping.schemas.homeshopping_schema import (
    # 편성표 관련 스키마
    HomeshoppingScheduleResponse,
    
    # 상품 검색 관련 스키마
    HomeshoppingSearchRequest,
    HomeshoppingSearchResponse,
    
    # 검색 이력 관련 스키마
    HomeshoppingSearchHistoryCreate,
    HomeshoppingSearchHistoryResponse,
    HomeshoppingSearchHistoryDeleteRequest,
    HomeshoppingSearchHistoryDeleteResponse,
    
    # 상품 상세 관련 스키마
    HomeshoppingProductDetailResponse,
    
    # 레시피 추천 관련 스키마
    RecipeRecommendationsResponse,
    
    # 스트리밍 관련 스키마
    HomeshoppingStreamResponse,
    
    # 찜 관련 스키마
    HomeshoppingLikesToggleRequest,
    HomeshoppingLikesToggleResponse,
    HomeshoppingLikesResponse,
    
    # 통합 알림 관련 스키마 (기존 테이블 활용)
    HomeshoppingNotificationListResponse
)

from services.homeshopping.crud.homeshopping_crud import (
    # 편성표 관련 CRUD
    get_homeshopping_schedule,
    
    # 상품 검색 관련 CRUD
    search_homeshopping_products,
    
    # 검색 이력 관련 CRUD
    add_homeshopping_search_history,
    get_homeshopping_search_history,
    delete_homeshopping_search_history,
    
    # 상품 상세 관련 CRUD
    get_homeshopping_product_detail,
    
    # 상품 분류 관련 CRUD
    get_homeshopping_classify_cls_ing,
    
    # 스트리밍 관련 CRUD
    get_homeshopping_live_url,
    
    # 찜 관련 CRUD
    toggle_homeshopping_likes,
    get_homeshopping_liked_products,
    
    # 통합 알림 관련 CRUD (기존 테이블 활용)
    mark_notification_as_read,
    get_notifications_with_filter,
    
    # KOK 상품 기반 홈쇼핑 추천 관련 CRUD
    recommend_homeshopping_to_kok,
    get_homeshopping_product_name,
    simple_recommend_homeshopping_to_kok
)
from common.keyword_extraction import extract_homeshopping_keywords

from services.recipe.crud.recipe_crud import recommend_by_recipe_pgvector

from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log

from common.logger import get_logger
logger = get_logger("homeshopping_router")

router = APIRouter(prefix="/api/homeshopping", tags=["HomeShopping"])


# ================================
# 편성표 관련 API
# ================================

@router.get("/schedule", response_model=HomeshoppingScheduleResponse)
async def get_schedule(
        request: Request,
        live_date: Optional[date] = Query(None, description="조회할 날짜 (YYYY-MM-DD 형식, 미입력시 전체 스케줄)"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 편성표 조회 (식품만)
    - live_date가 제공되면 해당 날짜의 스케줄만 조회
    - live_date가 미입력시 전체 스케줄 조회
    """
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 편성표 조회 요청: user_id={user_id}, live_date={live_date}")
    
    schedules = await get_homeshopping_schedule(db, live_date=live_date)
    
    # 편성표 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_schedule_view", 
            event_data={"live_date": live_date.isoformat() if live_date else None}
        )
    
    logger.info(f"홈쇼핑 편성표 조회 완료: user_id={user_id}, 결과 수={len(schedules)}")
    return {"schedules": schedules}


# ================================
# 스트리밍 관련 API
# ================================
BASE_DIR = Path(__file__).resolve().parent.parent # services/homeshopping
templates = Jinja2Templates(directory=str(BASE_DIR / "templates")) # services/homeshopping/templates

@router.get("/schedule/live-stream", response_class=HTMLResponse)
async def live_stream_html(
    request: Request,
    homeshopping_id: int | None = Query(None, description="홈쇼핑 ID (백엔드에서 m3u8 스트림 조회용)"),
    src: str | None = Query(None, description="직접 재생할 m3u8 URL (바로 재생용)"),
    db: AsyncSession = Depends(get_maria_service_db),
):
    """
    HLS.js HTML 템플릿 렌더링
    - src(직접 m3u8) 또는 homeshopping_id 중 하나를 받아서 재생 페이지 렌더
    - homeshopping_id가 주어지면 get_homeshopping_stream_info()로 m3u8 등 실제 스트림을 조회
    - 비동기 템플릿 렌더링, 인증은 선택적
    """
    stream_url = src
    title = "홈쇼핑 라이브"

    # homeshopping_id가 오면 백엔드에서 live_url 조회
    if not stream_url and homeshopping_id:
        live_url = await get_homeshopping_live_url(db, homeshopping_id)
        if not live_url:
            raise HTTPException(status_code=404, detail="방송을 찾을 수 없습니다.")
        stream_url = live_url

    if not stream_url:
        raise HTTPException(status_code=400, detail="src 또는 homeshopping_id 중 하나는 필수입니다.")

    # 선택: 사용자 로깅
    current_user = await get_current_user_optional(request)
    if current_user:
        # 비동기 백그라운드 처리: FastAPI BackgroundTasks를 추가 파라미터로 받아 사용해도 됨
        logger.info(f"[라이브 HTML] user_id={current_user.user_id}, stream={stream_url}")
        # """사용자 로그 전송(설명) - 스트림 페이지 조회 이벤트를 비동기로 적재한다"""
        await send_user_log(
            user_id=current_user.user_id,
            event_type="homeshopping_live_html_view",
            event_data={"stream_url": stream_url, "homeshopping_id": homeshopping_id},
        )

    # 템플릿 렌더
    return templates.TemplateResponse(
        "live_stream.html",
        {"request": request, "src": stream_url, "title": title},
    )


# ================================
# 상품 상세 관련 API
# ================================

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
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 상세 조회 요청: user_id={user_id}, live_id={live_id}")
    
    product_detail = await get_homeshopping_product_detail(db, live_id, user_id)
    if not product_detail:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    # 상품 상세 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_product_detail_view", 
            event_data={"live_id": live_id}
        )
    
    logger.info(f"홈쇼핑 상품 상세 조회 완료: user_id={user_id}, live_id={live_id}")
    return product_detail


# ================================
# 상품 추천 관련 API
# ================================

@router.get("/product/{product_id}/kok-recommend")
async def get_kok_recommendations(
        request: Request,
        product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품에 대한 콕 유사 상품 추천 조회
    """
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 콕 유사 상품 추천 조회 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # 추천 오케스트레이터 호출 (통합된 CRUD에서)        
        recommendations = await recommend_homeshopping_to_kok(
            db=db,
            homeshopping_product_id=product_id,
            k=5,  # 최대 5개
            use_rerank=False
        )
        
        logger.info(f"홈쇼핑 콕 유사 상품 추천 조회 완료: user_id={user_id}, product_id={product_id}, 결과 수={len(recommendations)}")
        return {"products": recommendations}
        
    except Exception as e:
        logger.error(f"홈쇼핑 콕 유사 상품 추천 조회 실패: product_id={product_id}, error={str(e)}")
        
        # 폴백: 간단한 추천 시스템 사용 (통합된 CRUD에서)
        try:
            fallback_recommendations = await simple_recommend_homeshopping_to_kok(
                homeshopping_product_id=product_id,
                k=5,
                db=db  # DB 전달하여 실제 DB 연동 시도
            )
            logger.info(f"폴백 추천 시스템 사용: {len(fallback_recommendations)}개 상품")
            return {"products": fallback_recommendations}
        except Exception as fallback_error:
            logger.error(f"폴백 추천 시스템도 실패: {str(fallback_error)}")
            # 최종 폴백: 빈 배열 반환
            return {"products": []}


@router.get("/product/{product_id}/check")
async def check_product_ingredient(
        request: Request,
        product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품의 식재료 여부 확인
    CLS_ING가 1(식재료)인지 여부만 확인
    """
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 식재료 여부 확인 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 확인
        cls_ing = await get_homeshopping_classify_cls_ing(db, product_id)
        
        if cls_ing == 1:
            # 식재료인 경우
            logger.info(f"홈쇼핑 상품 식재료 확인 완료: product_id={product_id}, cls_ing={cls_ing}")
            return {"is_ingredient": True}
        else:
            # 완제품인 경우
            logger.info(f"홈쇼핑 완제품으로 식재료 아님: product_id={product_id}, cls_ing={cls_ing}")
            return {"is_ingredient": False}
            
    except Exception as e:
        logger.error(f"홈쇼핑 상품 식재료 여부 확인 실패: product_id={product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="상품 식재료 여부 확인 중 오류가 발생했습니다.")

# ================================
# 레시피 추천 관련 API
# ================================

@router.get("/product/{product_id}/recipe-recommend", response_model=RecipeRecommendationsResponse)
async def get_recipe_recommendations_for_product(
        request: Request,
        product_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품에 대한 레시피 추천 조회
    - 상품명에서 키워드(식재료) 추출
    - 추출된 키워드를 기반으로 레시피 추천
    - recommend_by_recipe_pgvector를 method == "ingredient" 방식으로 사용
    """
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 레시피 추천 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # 1. 홈쇼핑 상품명 조회
        homeshopping_product_name = await get_homeshopping_product_name(db, product_id)
        if not homeshopping_product_name:
            raise HTTPException(status_code=404, detail="홈쇼핑 상품을 찾을 수 없습니다.")
        
        logger.info(f"상품명 조회 완료: product_id={product_id}, name={homeshopping_product_name}")
        
        # 2. 상품이 식재료인지 확인
        is_ingredient = await get_homeshopping_classify_cls_ing(db, product_id)
        
        # 3. 식재료가 아닌 경우 빈 응답 반환
        if not is_ingredient:
            logger.info(f"상품이 식재료가 아님: product_id={product_id}")
            return RecipeRecommendationsResponse(
                recipes=[],
                is_ingredient=False
            )
        
        # 4. 키워드 추출을 위한 표준 재료 어휘 로드 (MariaDB)
        # 홈쇼핑 전용 키워드 추출 로직 사용
        
        # 5. 상품명에서 키워드(식재료) 추출 (홈쇼핑 전용)
        keyword_result = extract_homeshopping_keywords(
            product_name=homeshopping_product_name,
            use_bigrams=True,
            drop_first_token=True,
            strip_digits=True,
            keep_longest_only=True
        )
        
        extracted_keywords = keyword_result["keywords"]
        logger.info(f"키워드 추출 완료: product_id={product_id}, keywords={extracted_keywords}")
        
        # 6. 추출된 키워드가 없으면 빈 응답 반환
        if not extracted_keywords:
            logger.info(f"추출된 키워드가 없음: product_id={product_id}")
            return RecipeRecommendationsResponse(
                recipes=[],
                is_ingredient=True
            )
        
        # 7. 키워드를 쉼표로 구분하여 레시피 추천 요청
        keywords_query = ",".join(extracted_keywords)
        logger.info(f"레시피 추천 요청: keywords={keywords_query}")
        
        # 8. recommend_by_recipe_pgvector를 method == "ingredient" 방식으로 호출
        # PostgreSQL DB 연결을 위한 import 추가
        from common.database.postgres_log import get_postgres_log_db
        from services.recipe.utils.recommend_service import get_db_vector_searcher
        
        # PostgreSQL DB 연결
        postgres_db = get_postgres_log_db()
        
        # VectorSearcher 인스턴스 생성
        vector_searcher = await get_db_vector_searcher()
        
        recipes_df = await recommend_by_recipe_pgvector(
            mariadb=db,
            postgres=postgres_db,
            vector_searcher=vector_searcher,
            query=keywords_query,
            method="ingredient",
            page=1,
            size=10,
            include_materials=True
        )
        
        # 9. DataFrame을 RecipeRecommendation 형태로 변환
        recipes = []
        if not recipes_df.empty:
            for _, row in recipes_df.iterrows():
                recipe = {
                    "recipe_id": int(row.get("RECIPE_ID", 0)),
                    "recipe_name": str(row.get("RECIPE_TITLE", "")),
                    "cooking_time": "30분",  # 기본값, 실제로는 DB에서 가져와야 함
                    "difficulty": "중급",     # 기본값, 실제로는 DB에서 가져와야 함
                    "ingredients": [],
                    "description": str(row.get("COOKING_INTRODUCTION", "")),
                    "recipe_image_url": str(row.get("THUMBNAIL_URL", "")) if row.get("THUMBNAIL_URL") else None
                }
                
                # 재료 정보가 있는 경우 추가
                if "MATERIALS" in row and row["MATERIALS"]:
                    for material in row["MATERIALS"]:
                        material_name = material.get("MATERIAL_NAME", "")
                        if material_name:
                            recipe["ingredients"].append(material_name)
                
                recipes.append(recipe)
        
        logger.info(f"레시피 추천 완료: product_id={product_id}, 레시피 수={len(recipes)}")
        
        # 10. 인증된 사용자의 경우에만 로그 기록
        if current_user and background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_recipe_recommendation", 
                event_data={
                    "product_id": product_id,
                    "homeshopping_product_name": homeshopping_product_name,
                    "extracted_keywords": extracted_keywords,
                    "recipe_count": len(recipes),
                    "is_ingredient": True
                }
            )
        
        return RecipeRecommendationsResponse(
            recipes=recipes,
            is_ingredient=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"홈쇼핑 상품 레시피 추천 실패: product_id={product_id}, user_id={user_id}, error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"레시피 추천 조회 중 오류가 발생했습니다: {str(e)}"
        )


# ================================
# 상품 검색 관련 API
# ================================

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
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    logger.info(f"홈쇼핑 상품 검색 요청: user_id={user_id}, keyword='{keyword}'")
    
    products = await search_homeshopping_products(db, keyword)
    
    # 검색 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search", 
            event_data={"keyword": keyword}
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
        search_data: HomeshoppingSearchHistoryCreate,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 저장
    """
    logger.info(f"홈쇼핑 검색 이력 저장 요청: user_id={current_user.user_id}, keyword='{search_data.keyword}'")
    
    try:
        saved_history = await add_homeshopping_search_history(db, current_user.user_id, search_data.keyword)
        await db.commit()
        
        # 검색 이력 저장 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_search_history_save", 
                event_data={"keyword": search_data.keyword}
            )
        
        logger.info(f"홈쇼핑 검색 이력 저장 완료: user_id={current_user.user_id}, history_id={saved_history['homeshopping_history_id']}")
        return saved_history
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 검색 이력 저장 실패: user_id={current_user.user_id}, keyword='{search_data.keyword}', error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 저장 중 오류가 발생했습니다.")


@router.get("/search/history", response_model=HomeshoppingSearchHistoryResponse)
async def get_search_history(
        limit: int = Query(5, ge=1, le=20, description="조회할 검색 이력 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 조회
    """
    logger.info(f"홈쇼핑 검색 이력 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    history = await get_homeshopping_search_history(db, current_user.user_id, limit)
    
    # 검색 이력 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_search_history_view", 
            event_data={"history_count": len(history)}
        )
    
    logger.info(f"홈쇼핑 검색 이력 조회 완료: user_id={current_user.user_id}, 결과 수={len(history)}")
    return {"history": history}


@router.delete("/search/history", response_model=HomeshoppingSearchHistoryDeleteResponse)
async def delete_search_history(
        delete_data: HomeshoppingSearchHistoryDeleteRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 검색 이력 삭제
    """
    logger.info(f"홈쇼핑 검색 이력 삭제 요청: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
    
    try:
        success = await delete_homeshopping_search_history(db, current_user.user_id, delete_data.homeshopping_history_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="삭제할 검색 이력을 찾을 수 없습니다.")
        
        await db.commit()
        
        # 검색 이력 삭제 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_search_history_delete", 
                event_data={"history_id": delete_data.homeshopping_history_id}
            )
        
        logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}")
        return {"message": "검색 이력이 삭제되었습니다."}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 검색 이력 삭제 실패: user_id={current_user.user_id}, history_id={delete_data.homeshopping_history_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="검색 이력 삭제 중 오류가 발생했습니다.")


# ================================
# 찜 관련 API
# ================================

@router.post("/likes/toggle", response_model=HomeshoppingLikesToggleResponse)
async def toggle_likes(
        like_data: HomeshoppingLikesToggleRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 찜 등록/해제
    """
    logger.info(f"홈쇼핑 찜 토글 요청: user_id={current_user.user_id}, product_id={like_data.product_id}")
    
    try:
        liked = await toggle_homeshopping_likes(db, current_user.user_id, like_data.product_id)
        await db.commit()
        
        # 찜 토글 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_likes_toggle", 
                event_data={"product_id": like_data.product_id, "liked": liked}
            )
        
        message = "찜이 등록되었습니다." if liked else "찜이 해제되었습니다."
        logger.info(f"홈쇼핑 찜 토글 완료: user_id={current_user.user_id}, product_id={like_data.product_id}, liked={liked}")
        
        return {
            "liked": liked,
            "message": message
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 찜 토글 실패: user_id={current_user.user_id}, product_id={like_data.product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜 토글 중 오류가 발생했습니다.")


@router.get("/likes", response_model=HomeshoppingLikesResponse)
async def get_liked_products(
        limit: int = Query(50, ge=1, le=100, description="조회할 찜한 상품 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 찜한 상품 목록 조회
    """
    logger.info(f"홈쇼핑 찜한 상품 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    liked_products = await get_homeshopping_liked_products(db, current_user.user_id, limit)
    
    # 찜한 상품 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_liked_products_view", 
            event_data={"liked_products_count": len(liked_products)}
        )
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    return {"liked_products": liked_products}


# ================================
# 통합 알림 관련 API
# ================================

@router.get("/notifications/orders", response_model=HomeshoppingNotificationListResponse)
async def get_order_notifications_api(
        limit: int = Query(20, ge=1, le=100, description="조회할 주문 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 상태 변경 알림만 조회
    """
    logger.info(f"홈쇼핑 주문 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="order_status",
            limit=limit, 
            offset=offset
        )
        
        # 주문 알림 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 주문 알림 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 주문 알림 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 알림 조회 중 오류가 발생했습니다.")


@router.get("/notifications/broadcasts", response_model=HomeshoppingNotificationListResponse)
async def get_broadcast_notifications_api(
        limit: int = Query(20, ge=1, le=100, description="조회할 방송 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 방송 시작 알림만 조회
    """
    logger.info(f"홈쇼핑 방송 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="broadcast_start",
            limit=limit, 
            offset=offset
        )
        
        # 방송 알림 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_broadcast_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 방송 알림 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 방송 알림 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="방송 알림 조회 중 오류가 발생했습니다.")


@router.get("/notifications/all", response_model=HomeshoppingNotificationListResponse)
async def get_all_notifications_api(
        limit: int = Query(20, ge=1, le=100, description="조회할 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 모든 알림 통합 조회 (주문 + 방송)
    """
    logger.info(f"홈쇼핑 모든 알림 통합 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            limit=limit, 
            offset=offset
        )
        
        # 모든 알림 통합 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_all_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                }
            )
        
        logger.info(f"홈쇼핑 모든 알림 통합 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 모든 알림 통합 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="모든 알림 통합 조회 중 오류가 발생했습니다.")


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read_api(
        notification_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 알림 읽음 처리
    """
    logger.info(f"홈쇼핑 알림 읽음 처리 요청: user_id={current_user.user_id}, notification_id={notification_id}")
    
    try:
        success = await mark_notification_as_read(db, current_user.user_id, notification_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        
        await db.commit()
        
        # 알림 읽음 처리 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_notification_read", 
                event_data={"notification_id": notification_id}
            )
        
        logger.info(f"홈쇼핑 알림 읽음 처리 완료: notification_id={notification_id}")
        return {"message": "알림이 읽음으로 표시되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 알림 읽음 처리 실패: notification_id={notification_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="알림 읽음 처리 중 오류가 발생했습니다.")
