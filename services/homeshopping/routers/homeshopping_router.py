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
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware
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
from common.http_dependencies import extract_http_info

from common.logger import get_logger
logger = get_logger("homeshopping_router", level="DEBUG")

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
    홈쇼핑 편성표 조회 (식품만) - 최적화된 버전
    - live_date가 제공되면 해당 날짜의 스케줄만 조회
    - live_date가 미입력시 전체 스케줄 조회
    - 제한 없이 모든 결과 반환
    """
    logger.debug(f"홈쇼핑 편성표 조회 시작: live_date={live_date}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning("인증되지 않은 사용자가 편성표 조회 요청")
    
    logger.info(f"홈쇼핑 편성표 조회 요청: user_id={user_id}, live_date={live_date}")
    
    try:
        logger.info(f"=== 라우터에서 get_homeshopping_schedule 호출 시작 ===")
        schedules = await get_homeshopping_schedule(
            db, 
            live_date=live_date
        )
        logger.info(f"=== 라우터에서 get_homeshopping_schedule 호출 완료: 결과={len(schedules)} ===")
        logger.debug(f"편성표 조회 성공: 결과 수={len(schedules)}")
    except Exception as e:
        logger.error(f"편성표 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="편성표 조회 중 오류가 발생했습니다.")
    
    # 편성표 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_schedule_view", 
            event_data={
                "live_date": live_date.isoformat() if live_date else None,
                "total_count": len(schedules)
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 편성표 조회 완료: user_id={user_id}, 결과 수={len(schedules)}")
    
    return {
        "schedules": schedules
    }


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
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
):
    """
    HLS.js HTML 템플릿 렌더링
    - src(직접 m3u8) 또는 homeshopping_id 중 하나를 받아서 재생 페이지 렌더
    - homeshopping_id가 주어지면 get_homeshopping_stream_info()로 m3u8 등 실제 스트림을 조회
    - 비동기 템플릿 렌더링, 인증은 선택적
    """
    logger.debug(f"라이브 스트림 HTML 요청: homeshopping_id={homeshopping_id}, src={src}")
    
    stream_url = src
    title = "홈쇼핑 라이브"

    # homeshopping_id가 오면 백엔드에서 live_url 조회
    if not stream_url and homeshopping_id:
        logger.debug(f"homeshopping_id로 라이브 URL 조회: homeshopping_id={homeshopping_id}")
        try:
            live_url = await get_homeshopping_live_url(db, homeshopping_id)
            if not live_url:
                logger.warning(f"라이브 URL을 찾을 수 없음: homeshopping_id={homeshopping_id}")
                raise HTTPException(status_code=404, detail="방송을 찾을 수 없습니다.")
            stream_url = live_url
            logger.debug(f"라이브 URL 조회 성공: {stream_url}")
        except Exception as e:
            logger.error(f"라이브 URL 조회 실패: homeshopping_id={homeshopping_id}, error={str(e)}")
            raise HTTPException(status_code=500, detail="라이브 URL 조회 중 오류가 발생했습니다.")

    if not stream_url:
        logger.warning("stream_url과 homeshopping_id 모두 없음")
        raise HTTPException(status_code=400, detail="src 또는 homeshopping_id 중 하나는 필수입니다.")

    # 선택: 사용자 로깅
    current_user = await get_current_user_optional(request)
    if current_user:
        # 비동기 백그라운드 처리: FastAPI BackgroundTasks를 사용
        logger.info(f"[라이브 HTML] user_id={current_user.user_id}, stream={stream_url}")
        # 사용자 로그 전송을 백그라운드 태스크로 처리
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=current_user.user_id,
                event_type="homeshopping_live_html_view",
                event_data={"stream_url": stream_url, "homeshopping_id": homeshopping_id},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
    else:
        logger.debug("인증되지 않은 사용자의 라이브 스트림 요청")

    # 템플릿 렌더
    logger.debug(f"라이브 스트림 HTML 템플릿 렌더링: stream_url={stream_url}")
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
    홈쇼핑 상품에 대한 콕 유사 상품 추천 조회 (캐싱 적용)
    """
    import time
    start_time = time.time()
    
    logger.debug(f"홈쇼핑 콕 유사 상품 추천 조회 시작: product_id={product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 KOK 추천 조회 요청: product_id={product_id}")
    
    logger.info(f"홈쇼핑 콕 유사 상품 추천 조회 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # 1. 캐시에서 먼저 조회
        from services.homeshopping.utils.memory_cache_manager import memory_cache_manager
        cached_recommendations = await memory_cache_manager.get_kok_recommendation_cache(
            product_id=product_id,
            k=5
        )
        
        if cached_recommendations is not None:
            elapsed_time = (time.time() - start_time) * 1000
            logger.debug(f"캐시에서 KOK 추천 결과 반환: product_id={product_id}, 결과 수={len(cached_recommendations)}, 응답시간={elapsed_time:.2f}ms")
            logger.info(f"캐시에서 KOK 추천 결과 반환: product_id={product_id}, 결과 수={len(cached_recommendations)}, 응답시간={elapsed_time:.2f}ms")
            return {"products": cached_recommendations}
        
        # 2. 캐시 미스 시 실제 추천 로직 실행
        logger.debug(f"캐시 미스 - 실제 추천 로직 실행: product_id={product_id}")
        recommendations = await recommend_homeshopping_to_kok(
            db=db,
            homeshopping_product_id=product_id,
            k=5,  # 최대 5개
            use_rerank=False
        )
        
        # 3. 결과를 캐시에 저장
        if recommendations:
            logger.debug(f"추천 결과를 캐시에 저장: product_id={product_id}, 결과 수={len(recommendations)}")
            await memory_cache_manager.set_kok_recommendation_cache(
                product_id=product_id,
                recommendations=recommendations,
                k=5
            )
        
        elapsed_time = (time.time() - start_time) * 1000
        logger.info(f"홈쇼핑 콕 유사 상품 추천 조회 완료: user_id={user_id}, product_id={product_id}, 결과 수={len(recommendations)}, 응답시간={elapsed_time:.2f}ms")
        return {"products": recommendations}
        
    except Exception as e:
        logger.error(f"홈쇼핑 콕 유사 상품 추천 조회 실패: product_id={product_id}, error={str(e)}")
        
        # 폴백: 간단한 추천 시스템 사용 (통합된 CRUD에서)
        logger.warning(f"메인 추천 시스템 실패, 폴백 시스템 사용: product_id={product_id}")
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
            logger.warning(f"모든 추천 시스템 실패, 빈 배열 반환: product_id={product_id}")
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
    logger.debug(f"홈쇼핑 상품 식재료 여부 확인 시작: product_id={product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 식재료 여부 확인 요청: product_id={product_id}")
    
    logger.info(f"홈쇼핑 상품 식재료 여부 확인 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 확인
        cls_ing = await get_homeshopping_classify_cls_ing(db, product_id)
        
        if cls_ing == 1:
            # 식재료인 경우
            logger.debug(f"상품이 식재료로 분류됨: product_id={product_id}, cls_ing={cls_ing}")
            logger.info(f"홈쇼핑 상품 식재료 확인 완료: product_id={product_id}, cls_ing={cls_ing}")
            return {"is_ingredient": True}
        else:
            # 완제품인 경우
            logger.debug(f"상품이 완제품으로 분류됨: product_id={product_id}, cls_ing={cls_ing}")
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
    logger.debug(f"홈쇼핑 상품 레시피 추천 시작: product_id={product_id}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning(f"인증되지 않은 사용자가 레시피 추천 요청: product_id={product_id}")
    
    logger.info(f"홈쇼핑 상품 레시피 추천 요청: user_id={user_id}, product_id={product_id}")
    
    try:
        # 1. 홈쇼핑 상품명 조회
        logger.debug(f"홈쇼핑 상품명 조회: product_id={product_id}")
        homeshopping_product_name = await get_homeshopping_product_name(db, product_id)
        if not homeshopping_product_name:
            logger.warning(f"홈쇼핑 상품을 찾을 수 없음: product_id={product_id}")
            raise HTTPException(status_code=404, detail="홈쇼핑 상품을 찾을 수 없습니다.")
        
        logger.debug(f"상품명 조회 성공: product_id={product_id}, name={homeshopping_product_name}")
        logger.info(f"상품명 조회 완료: product_id={product_id}, name={homeshopping_product_name}")
        
        # 2. 상품이 식재료인지 확인
        logger.debug(f"상품 식재료 여부 확인: product_id={product_id}")
        is_ingredient = await get_homeshopping_classify_cls_ing(db, product_id)
        
        # 3. 식재료가 아닌 경우 빈 응답 반환
        if not is_ingredient:
            logger.debug(f"상품이 식재료가 아님 - 빈 응답 반환: product_id={product_id}")
            logger.info(f"상품이 식재료가 아님: product_id={product_id}")
            return RecipeRecommendationsResponse(
                recipes=[],
                is_ingredient=False,
                extracted_keywords=[]
            )
        
        # 4. 키워드 추출을 위한 표준 재료 어휘 로드 (MariaDB)
        # 홈쇼핑 전용 키워드 추출 로직 사용
        
        # 5. 상품명에서 키워드(식재료) 추출 (홈쇼핑 전용)
        logger.debug(f"키워드 추출 시작: product_id={product_id}, product_name={homeshopping_product_name}")
        keyword_result = extract_homeshopping_keywords(
            product_name=homeshopping_product_name,
            use_bigrams=True,
            drop_first_token=True,
            strip_digits=True,
            keep_longest_only=True
        )
        
        extracted_keywords = keyword_result["keywords"]
        logger.debug(f"키워드 추출 결과: product_id={product_id}, keywords={extracted_keywords}")
        logger.info(f"키워드 추출 완료: product_id={product_id}, keywords={extracted_keywords}")
        
        # 6. 추출된 키워드가 없으면 빈 응답 반환
        if not extracted_keywords:
            logger.debug(f"추출된 키워드가 없음 - 빈 응답 반환: product_id={product_id}")
            logger.info(f"추출된 키워드가 없음: product_id={product_id}")
            return RecipeRecommendationsResponse(
                recipes=[],
                is_ingredient=True,
                extracted_keywords=[]
            )
        
        # 7. 키워드를 쉼표로 구분하여 레시피 추천 요청
        keywords_query = ",".join(extracted_keywords)
        logger.debug(f"레시피 추천 쿼리 생성: keywords_query={keywords_query}")
        logger.info(f"레시피 추천 요청: keywords={keywords_query}")
        
        # 8. recommend_by_recipe_pgvector를 method == "ingredient" 방식으로 호출
        # PostgreSQL DB 연결을 위한 import 추가
        logger.debug("PostgreSQL DB 연결 및 VectorSearcher 초기화")
        from common.database.postgres_log import get_postgres_log_db
        from services.recipe.utils.recommend_service import get_db_vector_searcher
        
        # PostgreSQL DB 연결
        postgres_db = get_postgres_log_db()
        
        # VectorSearcher 인스턴스 생성
        vector_searcher = await get_db_vector_searcher()
        
        logger.debug(f"레시피 추천 실행: method=ingredient, query={keywords_query}")
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
        logger.debug(f"레시피 추천 결과: DataFrame 크기={len(recipes_df)}")
        
        # 9. DataFrame을 RecipeRecommendation 형태로 변환
        logger.debug("DataFrame을 RecipeRecommendation 형태로 변환 시작")
        recipes = []
        if not recipes_df.empty:
            logger.debug(f"레시피 데이터 변환: {len(recipes_df)}개 레시피 처리")
            for _, row in recipes_df.iterrows():
                recipe = {
                    "recipe_id": int(row.get("RECIPE_ID", 0)),
                    "recipe_name": str(row.get("RECIPE_TITLE", "")),
                    "scrap_count": int(row.get("SCRAP_COUNT", 0)) if row.get("SCRAP_COUNT") else None,
                    "ingredients": [],
                    "description": str(row.get("COOKING_INTRODUCTION", "")),
                    "recipe_image_url": str(row.get("THUMBNAIL_URL", "")) if row.get("THUMBNAIL_URL") else None,
                    "number_of_serving": str(row.get("NUMBER_OF_SERVING", "")) if row.get("NUMBER_OF_SERVING") else None
                }
                
                # 재료 정보가 있는 경우 추가
                if "MATERIALS" in row and row["MATERIALS"]:
                    for material in row["MATERIALS"]:
                        material_name = material.get("MATERIAL_NAME", "")
                        if material_name:
                            recipe["ingredients"].append(material_name)
                
                recipes.append(recipe)
        else:
            logger.debug("추천된 레시피가 없음")
        
        logger.debug(f"레시피 변환 완료: {len(recipes)}개 레시피 생성")
        logger.info(f"레시피 추천 완료: product_id={product_id}, 레시피 수={len(recipes)}")
        
        # 10. 인증된 사용자의 경우에만 로그 기록
        if current_user and background_tasks:
            http_info = extract_http_info(request, response_code=200)
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
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return RecipeRecommendationsResponse(
            recipes=recipes,
            is_ingredient=True,
            extracted_keywords=extracted_keywords
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


# ================================
# 찜 관련 API
# ================================

@router.post("/likes/toggle", response_model=HomeshoppingLikesToggleResponse)
async def toggle_likes(
        request: Request,
        like_data: HomeshoppingLikesToggleRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 상품 찜 등록/해제
    """
    logger.debug(f"홈쇼핑 찜 토글 시작: user_id={current_user.user_id}, live_id={like_data.live_id}")
    logger.info(f"홈쇼핑 찜 토글 요청: user_id={current_user.user_id}, live_id={like_data.live_id}")
    
    try:
        liked = await toggle_homeshopping_likes(db, current_user.user_id, like_data.live_id)
        await db.commit()
        logger.debug(f"찜 토글 성공: user_id={current_user.user_id}, live_id={like_data.live_id}, liked={liked}")
        
        # 찜 토글 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_likes_toggle", 
                event_data={"live_id": like_data.live_id, "liked": liked},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        message = "찜이 등록되었습니다." if liked else "찜이 해제되었습니다."
        logger.info(f"홈쇼핑 찜 토글 완료: user_id={current_user.user_id}, live_id={like_data.live_id}, liked={liked}")
        
        return {
            "liked": liked,
            "message": message
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 찜 토글 실패: user_id={current_user.user_id}, live_id={like_data.live_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜 토글 중 오류가 발생했습니다.")


@router.get("/likes", response_model=HomeshoppingLikesResponse)
async def get_liked_products(
        request: Request,
        limit: int = Query(50, ge=1, le=100, description="조회할 찜한 상품 개수"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 찜한 상품 목록 조회
    """
    logger.debug(f"홈쇼핑 찜한 상품 조회 시작: user_id={current_user.user_id}, limit={limit}")
    logger.info(f"홈쇼핑 찜한 상품 조회 요청: user_id={current_user.user_id}, limit={limit}")
    
    try:
        liked_products = await get_homeshopping_liked_products(db, current_user.user_id, limit)
        logger.debug(f"찜한 상품 조회 성공: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    except Exception as e:
        logger.error(f"찜한 상품 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="찜한 상품 조회 중 오류가 발생했습니다.")
    
    # 찜한 상품 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_liked_products_view", 
            event_data={"liked_products_count": len(liked_products)},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={current_user.user_id}, 결과 수={len(liked_products)}")
    return {"liked_products": liked_products}


# ================================
# 통합 알림 관련 API
# ================================

@router.get("/notifications/orders", response_model=HomeshoppingNotificationListResponse)
async def get_order_notifications_api(
        request: Request,
        limit: int = Query(20, ge=1, le=100, description="조회할 주문 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 상태 변경 알림만 조회
    """
    logger.debug(f"홈쇼핑 주문 알림 조회 시작: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"홈쇼핑 주문 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="order_status",
            limit=limit, 
            offset=offset
        )
        logger.debug(f"주문 알림 조회 성공: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체={total_count}")
        
        # 주문 알림 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
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
        request: Request,
        limit: int = Query(20, ge=1, le=100, description="조회할 방송 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 방송 시작 알림만 조회
    """
    logger.debug(f"홈쇼핑 방송 알림 조회 시작: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"홈쇼핑 방송 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="broadcast_start",
            limit=limit, 
            offset=offset
        )
        logger.debug(f"방송 알림 조회 성공: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체={total_count}")
        
        # 방송 알림 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_broadcast_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
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
        request: Request,
        limit: int = Query(20, ge=1, le=100, description="조회할 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 모든 알림 통합 조회 (주문 + 방송)
    """
    logger.debug(f"홈쇼핑 모든 알림 통합 조회 시작: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"홈쇼핑 모든 알림 통합 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            limit=limit, 
            offset=offset
        )
        logger.debug(f"모든 알림 통합 조회 성공: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체={total_count}")
        
        # 모든 알림 통합 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_all_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
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
        request: Request,
        notification_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 알림 읽음 처리
    """
    logger.debug(f"홈쇼핑 알림 읽음 처리 시작: user_id={current_user.user_id}, notification_id={notification_id}")
    logger.info(f"홈쇼핑 알림 읽음 처리 요청: user_id={current_user.user_id}, notification_id={notification_id}")
    
    try:
        success = await mark_notification_as_read(db, current_user.user_id, notification_id)
        
        if not success:
            logger.warning(f"알림을 찾을 수 없음: notification_id={notification_id}")
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        
        await db.commit()
        logger.debug(f"알림 읽음 처리 성공: notification_id={notification_id}")
        
        # 알림 읽음 처리 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_notification_read", 
                event_data={"notification_id": notification_id},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 알림 읽음 처리 완료: notification_id={notification_id}")
        return {"message": "알림이 읽음으로 표시되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 알림 읽음 처리 실패: notification_id={notification_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="알림 읽음 처리 중 오류가 발생했습니다.")
