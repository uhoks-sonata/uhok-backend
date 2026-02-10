from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user_optional
from common.http_dependencies import extract_http_info
from common.keyword_extraction import extract_homeshopping_keywords
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.classify_crud import get_homeshopping_classify_cls_ing
from services.homeshopping.crud.recommendation_crud import (
    get_homeshopping_product_name,
    recommend_homeshopping_to_kok,
    simple_recommend_homeshopping_to_kok,
)
from services.homeshopping.schemas.recipe_schema import RecipeRecommendationsResponse
from services.homeshopping.utils.cache_manager import cache_manager
from services.recipe.crud.recipe_search_crud import recommend_by_recipe_pgvector_v2
from services.recipe.utils.remote_ml_adapter import get_remote_ml_searcher

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()


@router.post("/cache/invalidate/kok-recommend")
async def invalidate_kok_recommend_cache(
        product_id: Optional[int] = Query(None, description="특정 상품 캐시만 무효화할 경우 상품 ID")
):
    """
    홈쇼핑 KOK 추천 캐시 무효화
    - product_id 미입력: 전체 KOK 추천 캐시 삭제
    - product_id 입력: 해당 상품 KOK 추천 캐시만 삭제
    """
    logger.debug(f"KOK 추천 캐시 무효화 시작: product_id={product_id}")

    try:
        deleted_count = await cache_manager.invalidate_kok_recommendation_cache(product_id=product_id)
        logger.info(f"KOK 추천 캐시 무효화 완료: product_id={product_id}, 삭제된 키 수={deleted_count}")
        return {"message": "KOK 추천 캐시가 무효화되었습니다.", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"KOK 추천 캐시 무효화 실패: product_id={product_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 무효화 중 오류가 발생했습니다: {str(e)}")


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
        # 1. 캐시에서 먼저 조회 (Redis)
        cached_recommendations = await cache_manager.get_kok_recommendation_cache(
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
        
        # 3. 결과를 캐시에 저장 (Redis)
        if recommendations:
            logger.debug(f"추천 결과를 캐시에 저장: product_id={product_id}, 결과 수={len(recommendations)}")
            await cache_manager.set_kok_recommendation_cache(
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
        
        # 8. recommend_by_recipe_pgvector_v2를 원격 ML 벡터 검색 어댑터와 함께 호출
        logger.debug("원격 ML 벡터 검색 어댑터 초기화")
        vector_searcher = await get_remote_ml_searcher()
        
        logger.debug(f"레시피 추천 실행: method=ingredient, query={keywords_query}")
        recipes_df = await recommend_by_recipe_pgvector_v2(
            mariadb=db,
            postgres=None,
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

