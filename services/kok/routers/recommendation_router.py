from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user
from common.database.mariadb_service import get_maria_service_db
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.user.schemas.profile_schema import UserOut
from services.homeshopping.schemas.kok_recommendation_schema import (
    KokHomeshoppingRecommendationProduct,
    KokHomeshoppingRecommendationResponse,
)
from services.homeshopping.crud.kok_recommendation_crud import (
    get_kok_product_name_by_id,
    get_homeshopping_recommendations_by_kok,
    get_homeshopping_recommendations_fallback,
)
from services.kok.crud.cart_crud import get_kok_cart_items
from services.kok.crud.likes_crud import get_kok_liked_products
from services.kok.utils.kok_homeshopping import get_recommendation_strategy

logger = get_logger("kok_router")
router = APIRouter()

@router.get("/product/homeshopping-recommend")
async def get_homeshopping_recommend(
    request: Request,
    k: int = Query(5, ge=1, le=20, description="추천 상품 개수"),
    background_tasks: BackgroundTasks = None,
    current_user: UserOut = Depends(get_current_user),
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    현재 사용자의 KOK 찜/장바구니 상품을 기반으로 유사한 홈쇼핑 상품 추천
    - 사용자의 찜 목록과 장바구니 목록에서 kok_product_id 자동 수집
    - KOK utils의 추천 알고리즘 사용
    """
    logger.debug(f"홈쇼핑 추천 시작: user_id={current_user.user_id}, k={k}")
    
    try:
        user_id = current_user.user_id
        logger.info(f"홈쇼핑 추천 요청: user_id={user_id}, k={k}")
        
        # 1. 현재 사용자의 KOK 찜 목록과 장바구니 목록에서 kok_product_id 수집
        logger.debug("사용자의 찜 목록과 장바구니 목록에서 상품 ID 수집 시작")
        # 찜한 상품들의 kok_product_id 수집
        liked_products = await get_kok_liked_products(db, user_id, limit=100)
        liked_product_ids = [product["kok_product_id"] for product in liked_products]
        
        # 장바구니 상품들의 kok_product_id 수집
        cart_items = await get_kok_cart_items(db, user_id, limit=100)
        cart_product_ids = [item["kok_product_id"] for item in cart_items]
        
        # 중복 제거하여 고유한 kok_product_id 목록 생성
        all_product_ids = list(set(liked_product_ids + cart_product_ids))
        
        if not all_product_ids:
            logger.warning(f"찜하거나 장바구니에 담긴 상품이 없음: user_id={user_id}")
            raise HTTPException(status_code=400, detail="찜하거나 장바구니에 담긴 상품이 없습니다.")
        
        logger.info(f"수집된 KOK 상품 ID: 찜={len(liked_product_ids)}개, 장바구니={len(cart_product_ids)}개, 총={len(all_product_ids)}개")
        
        # 2. 각 KOK 상품명 조회 및 추천 키워드 수집        
        logger.debug("각 KOK 상품명 조회 및 추천 키워드 수집 시작")
        all_search_terms = set()
        kok_product_names = []
        
        for product_id in all_product_ids:
            try:
                kok_product_name = await get_kok_product_name_by_id(db, product_id)
                if kok_product_name:
                    kok_product_names.append(kok_product_name)
                    # 각 상품명에서 추천 키워드 추출
                    try:
                        recommendation_result = get_recommendation_strategy(kok_product_name, 5) # 각 상품당 최대 5개
                        if recommendation_result and recommendation_result.get("status") == "success":
                            search_terms = recommendation_result.get("search_terms", [])
                            all_search_terms.update(search_terms)
                            logger.info(f"상품 '{kok_product_name}'에서 추출된 키워드: {search_terms}")
                        else:
                            logger.warning(f"상품 '{kok_product_name}'에서 키워드 추출 실패: {recommendation_result}")
                    except Exception as e:
                        logger.error(f"상품 '{kok_product_name}' 키워드 추출 중 오류: {str(e)}")
                        continue
            except Exception as e:
                logger.warning(f"상품 ID {product_id} 조회 실패: {str(e)}")
                continue
        
        if not all_search_terms:
            logger.warning(f"추천 키워드를 추출할 수 없음: user_id={user_id}")
            raise HTTPException(status_code=400, detail="추천 키워드를 추출할 수 없습니다.")
        
        logger.info(f"추출된 추천 키워드: {list(all_search_terms)}")
        
        # 3. 각 KOK 상품별로 홈쇼핑 상품 추천 조회 (각각 최대 5개씩)        
        logger.debug("각 KOK 상품별로 홈쇼핑 상품 추천 조회 시작")
        all_recommendations = []
        product_recommendations = {}  # 각 상품별 추천 결과를 저장
        
        # 각 KOK 상품별로 추천 조회
        for product_id, product_name in zip(all_product_ids, kok_product_names):
            if not product_name:
                continue
                
            try:
                # 각 상품명에서 추천 키워드 추출
                recommendation_result = get_recommendation_strategy(product_name, 5)  # 각 상품당 최대 5개
                if not recommendation_result or recommendation_result.get("status") != "success":
                    logger.warning(f"상품 '{product_name}'에서 키워드 추출 실패: {recommendation_result}")
                    continue
                search_terms = recommendation_result.get("search_terms", [])
                if not search_terms:
                    logger.warning(f"상품 '{product_name}'에서 추출된 키워드가 없음")
                    continue
                logger.info(f"상품 '{product_name}'에서 추출된 키워드: {search_terms}")
                
                # 검색 조건을 더 유연하게 구성
                search_conditions = []
                for term in search_terms:
                    # 정확한 키워드 매칭
                    search_conditions.append(f"c.PRODUCT_NAME LIKE '%{term}%'")
                    # 브랜드명 매칭 (대괄호 안의 내용)
                    if '[' in product_name and ']' in product_name:
                        brand = product_name.split('[')[1].split(']')[0]
                        search_conditions.append(f"c.PRODUCT_NAME LIKE '%{brand}%'")
                
                # 해당 상품에 대한 추천 조회
                logger.debug(f"상품 '{product_name}'에 대한 홈쇼핑 추천 조회 시작")
                product_recs = await get_homeshopping_recommendations_by_kok(
                    db, product_name, search_conditions, 5
                )
                
                if not product_recs:
                    # 폴백: 상품명에서 주요 키워드만 추출하여 검색
                    logger.debug(f"상품 '{product_name}' 추천 실패, 폴백 시스템 사용")
                    fallback_keywords = [term for term in search_terms if len(term) > 1]
                    if fallback_keywords:
                        fallback_recs = await get_homeshopping_recommendations_fallback(
                            db, fallback_keywords[0], 5
                        )
                        if fallback_recs:
                            product_recs = fallback_recs
                            logger.debug(f"폴백 시스템으로 추천 성공: {len(product_recs)}개")
                
                # 결과 저장
                product_recommendations[product_name] = product_recs
                all_recommendations.extend(product_recs)
                
                logger.info(f"상품 '{product_name}' 추천 완료: {len(product_recs)}개")
                
            except Exception as e:
                logger.error(f"상품 '{product_name}' 추천 실패: {e}")
                product_recommendations[product_name] = []
                continue
        
        # 전체 추천 결과에서 중복 제거 (product_id 기준)
        logger.debug("전체 추천 결과에서 중복 제거 시작")
        seen_product_ids = set()
        final_recommendations = []
        for rec in all_recommendations:
            if rec["product_id"] not in seen_product_ids:
                final_recommendations.append(rec)
                seen_product_ids.add(rec["product_id"])
        
        logger.info(f"전체 추천 결과: {len(final_recommendations)}개 (중복 제거 후)")
        
        algorithm_info = {
            "algorithm": "multi_product_keyword_based",
            "status": "success",
            "search_terms": ", ".join(all_search_terms),
            "source_products_count": str(len(all_product_ids)),
            "liked_products_count": str(len(liked_product_ids)),
            "cart_products_count": str(len(cart_product_ids)),
            "total_recommendations": str(len(final_recommendations)),
            "product_recommendations_count": str(len(product_recommendations))
        }
        
        # 5. 응답 데이터 구성
        response_products = []
        for rec in final_recommendations:
            response_products.append(KokHomeshoppingRecommendationProduct(
                product_id=rec["product_id"],
                product_name=rec["product_name"],
                store_name=rec["store_name"],
                sale_price=rec["sale_price"],
                dc_price=rec["dc_price"],
                dc_rate=rec["dc_rate"],
                thumb_img_url=rec["thumb_img_url"],
                live_date=rec["live_date"],
                live_start_time=rec["live_start_time"],
                live_end_time=rec["live_end_time"],
                similarity_score=None  # 향후 유사도 점수 계산 로직 추가 가능
            ))
        
        # 각 상품별 추천 결과를 스키마 형태로 변환
        product_recommendations_response = {}
        for product_name, recs in product_recommendations.items():
            product_recommendations_response[product_name] = []
            for rec in recs:
                product_recommendations_response[product_name].append(KokHomeshoppingRecommendationProduct(
                    product_id=rec["product_id"],
                    product_name=rec["product_name"],
                    store_name=rec["store_name"],
                    sale_price=rec["sale_price"],
                    dc_price=rec["dc_price"],
                    dc_rate=rec["dc_rate"],
                    thumb_img_url=rec["thumb_img_url"],
                    live_date=rec["live_date"],
                    live_start_time=rec["live_start_time"],
                    live_end_time=rec["live_end_time"],
                    similarity_score=None
                ))
        
        # 6. 사용자 활동 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="kok_homeshopping_recommendation", 
                event_data={
                    "source_products_count": len(all_product_ids),
                    "liked_products_count": len(liked_product_ids),
                    "cart_products_count": len(cart_product_ids),
                    "recommendation_count": len(response_products),
                    "algorithm": "multi_product_keyword_based",
                    "k": k
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 추천 완료: user_id={user_id}, 소스 상품={len(all_product_ids)}개, 결과 수={len(response_products)}개")
        
        return KokHomeshoppingRecommendationResponse(
            kok_product_id=None,  # 단일 상품이 아닌 다중 상품 기반
            kok_product_name="사용자 맞춤 추천",  # 다중 상품 기반임을 표시
            recommendations=response_products,
            total_count=len(response_products),
            algorithm_info=algorithm_info,
            product_recommendations=product_recommendations_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"홈쇼핑 추천 API 오류: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"홈쇼핑 추천 중 오류가 발생했습니다: {str(e)}"
        )
